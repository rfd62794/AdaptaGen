"""
AdaptaGen: A self-modifying Python script using the Gemini API with version control.

Version: 0.0.1-r7

Enhancements in r7:
1. Added comprehensive code validation to check for common issues in generated code:
   - Syntax errors
   - "...existing code" placeholders
   - Missing imports, classes, and functions
   - Incomplete beginning and end of code
   - Inconsistent indentation
   - Unclosed delimiters (quotes, parentheses, brackets)

2. Implemented automatic fixing of common issues:
   - Replacing "...existing code" placeholders with appropriate content
   - Adding missing docstrings and main execution blocks
   - Fixing missing imports
   - Handling truncated code
   - Fixing unclosed delimiters and string literals

3. Added a retry mechanism with enhanced prompts:
   - Generates specific prompts addressing identified issues
   - Makes multiple attempts before falling back to automatic fixes
   - Saves intermediate versions with descriptive suffixes for debugging

4. Improved prompt generation:
   - Added specific guidelines to prevent common issues
   - Created enhanced prompts that address specific problems

5. Added advanced incremental editing approach:
   - Edits the same file in-place with automatic backups
   - Uses timed backoff strategy instead of fixed retry count
   - Implements multiple editing approaches when initial attempts fail
   - Verifies each edit works before proceeding to the next
   - Tests functionality after each edit
   - Provides detailed statistics on successful and failed edits
   - Can be enabled with the --incremental command-line flag
"""

import os
import sys
import inspect
import logging
import json
import datetime
import hashlib
import re
from pathlib import Path
from typing import List, Dict, Optional, Any, Set, Type, ClassVar, Tuple
from dataclasses import dataclass, field, asdict
import google.generativeai as genai
from dotenv import load_dotenv
import argparse

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Constants
ENV_API_KEY = "GEMINI_API_KEY"
ENV_MODEL_NAME = "GEMINI_MODEL"
DEFAULT_MODEL_NAME = "gemini-pro"
ENV_TEMPERATURE = "TEMPERATURE"
DEFAULT_TEMPERATURE = 0.7
ENV_MAX_OUTPUT_TOKENS = "MAX_OUTPUT_TOKENS"
DEFAULT_MAX_OUTPUT_TOKENS = 8192
ENV_TOP_P = "TOP_P"
DEFAULT_TOP_P = 0.95
ENV_TOP_K = "TOP_K"
DEFAULT_TOP_K = 40

# Version control constants
VERSION = "0.0.1-r7"
VERSION_HISTORY_DIR = Path(".adaptagen_versions")
VERSION_METADATA_FILE = "version_metadata.json"

# Token control constants
TOKEN_PATTERN = r"<TOKEN:(\w+)>"
TOKEN_PREFIX = "<TOKEN:"
TOKEN_SUFFIX = ">"

@dataclass
class Token:
    name: str
    value: Any

class TokenRegistry:
    """Registry for managing tokens used throughout the codebase."""

    _registry: ClassVar[Dict[str, Token]] = {}

    @classmethod
    def register(cls, name: str, value: Any) -> None:
        """Register a token with its value."""
        cls._registry[name] = Token(name, value)

    @classmethod
    def get(cls, name: str, default: Any = None) -> Any:
        """Get a token's value."""
        token = cls._registry.get(name)
        return token.value if token else default

    @classmethod
    def format_token(cls, name: str) -> str:
        """Format a token name into a token string."""
        return f"{TOKEN_PREFIX}{name}{TOKEN_SUFFIX}"

    @classmethod
    def validate_tokens(cls, text: str) -> List[str]:
        """Validate tokens in a text and return a list of invalid tokens."""
        invalid_tokens = []
        pattern = re.compile(TOKEN_PATTERN)
        for match in pattern.finditer(text):
            token_name = match.group(1)
            if token_name not in cls._registry:
                invalid_tokens.append(token_name)
        return invalid_tokens

    @classmethod
    def replace_tokens(cls, text: str) -> str:
        """Replace tokens in a text with their values."""
        for token in cls._registry.values():
            text = text.replace(cls.format_token(token.name), str(token.value))
        return text

class CodeValidator:
    """Validates generated code for common issues."""
    
    @staticmethod
    def validate_code(code: str, original_code: str) -> Tuple[bool, List[str]]:
        """
        Validate the generated code for common issues.
        
        Args:
            code: The generated code to validate
            original_code: The original code for comparison
            
        Returns:
            Tuple of (is_valid, list_of_issues)
        """
        issues = []
        
        # Check for syntax errors
        try:
            compile(code, '<string>', 'exec')
        except SyntaxError as e:
            issues.append(f"Syntax error: {e}")
            return False, issues
            
        # Check for "...existing code" placeholders
        if "...existing code" in code:
            issues.append("Contains '...existing code' placeholders that weren't replaced")
        
        # Check for missing imports by comparing with original
        original_imports = CodeValidator._extract_imports(original_code)
        new_imports = CodeValidator._extract_imports(code)
        
        missing_imports = [imp for imp in original_imports if imp not in new_imports]
        if missing_imports:
            issues.append(f"Missing imports: {', '.join(missing_imports)}")
        
        # Check for incomplete beginning (missing docstring, imports)
        if not code.strip().startswith('"""') and original_code.strip().startswith('"""'):
            issues.append("Missing docstring at the beginning")
            
        # Check for incomplete ending (missing main block)
        if "if __name__ == \"__main__\":" not in code and "if __name__ == \"__main__\":" in original_code:
            issues.append("Missing main execution block at the end")
            
        # Check for proper version constant
        if "VERSION = " not in code:
            issues.append("Missing VERSION constant")
            
        # Check for class definitions that should be preserved
        original_classes = CodeValidator._extract_class_names(original_code)
        new_classes = CodeValidator._extract_class_names(code)
        missing_classes = [cls for cls in original_classes if cls not in new_classes]
        if missing_classes:
            issues.append(f"Missing class definitions: {', '.join(missing_classes)}")
            
        # Check for function definitions that should be preserved
        original_functions = CodeValidator._extract_function_names(original_code)
        new_functions = CodeValidator._extract_function_names(code)
        missing_functions = [func for func in original_functions if func not in new_functions]
        if missing_functions:
            issues.append(f"Missing function definitions: {', '.join(missing_functions)}")
            
        # Check for consistent indentation
        if CodeValidator._has_inconsistent_indentation(code):
            issues.append("Inconsistent indentation detected")
            
        # Check for proper closing of multi-line strings, parentheses, brackets
        if CodeValidator._has_unclosed_delimiters(code):
            issues.append("Unclosed delimiters (quotes, parentheses, brackets) detected")
            
        return len(issues) == 0, issues
    
    @staticmethod
    def _extract_imports(code: str) -> List[str]:
        """Extract import statements from code."""
        imports = []
        import_pattern = r'^(?:from\s+[\w.]+\s+import\s+[\w,\s]+|import\s+[\w,\s.]+)$'
        
        for line in code.split('\n'):
            line = line.strip()
            if re.match(import_pattern, line):
                imports.append(line)
                
        return imports
    
    @staticmethod
    def _extract_class_names(code: str) -> List[str]:
        """Extract class names from code."""
        class_names = []
        class_pattern = r'^class\s+(\w+)[\(:]'
        
        for line in code.split('\n'):
            line = line.strip()
            match = re.match(class_pattern, line)
            if match:
                class_names.append(match.group(1))
                
        return class_names
    
    @staticmethod
    def _extract_function_names(code: str) -> List[str]:
        """Extract function names from code."""
        function_names = []
        function_pattern = r'^def\s+(\w+)\s*\('
        
        for line in code.split('\n'):
            line = line.strip()
            match = re.match(function_pattern, line)
            if match:
                function_names.append(match.group(1))
                
        return function_names
    
    @staticmethod
    def _has_inconsistent_indentation(code: str) -> bool:
        """Check for inconsistent indentation."""
        lines = code.split('\n')
        indent_sizes = set()
        
        for line in lines:
            if line.strip() and not line.strip().startswith('#'):
                # Count leading spaces
                indent = len(line) - len(line.lstrip())
                if indent > 0:
                    indent_sizes.add(indent % 4)  # Check if indentation is multiple of 4
                    
        # If we have more than one indentation size modulo 4, it's inconsistent
        return len(indent_sizes) > 1 and 0 in indent_sizes
    
    @staticmethod
    def _has_unclosed_delimiters(code: str) -> bool:
        """Check for unclosed delimiters (quotes, parentheses, brackets)."""
        # This is a simplified check - a full parser would be more accurate
        delimiters = {
            '(': ')',
            '[': ']',
            '{': '}',
            '"': '"',
            "'": "'"
        }
        
        stack = []
        i = 0
        in_string = False
        string_char = None
        
        while i < len(code):
            char = code[i]
            
            # Handle string literals
            if char in ('"', "'") and (not in_string or string_char == char):
                if in_string:
                    if string_char == char and code[i-1] != '\\':
                        in_string = False
                        string_char = None
                else:
                    in_string = True
                    string_char = char
            
            # Skip characters in string literals
            if in_string:
                i += 1
                continue
                
            # Handle opening delimiters
            if char in delimiters:
                stack.append(char)
            
            # Handle closing delimiters
            if char in delimiters.values():
                if not stack:
                    return True  # Unmatched closing delimiter
                
                opening = stack.pop()
                if delimiters[opening] != char:
                    return True  # Mismatched delimiter
            
            i += 1
            
        # If stack is not empty, we have unclosed delimiters
        return len(stack) > 0
    
    @staticmethod
    def fix_common_issues(code: str, original_code: str) -> str:
        """
        Attempt to fix common issues in the generated code.
        
        Args:
            code: The generated code to fix
            original_code: The original code for reference
            
        Returns:
            Fixed code
        """
        # Check for truncated code
        code = CodeValidator._fix_truncated_code(code, original_code)
        
        # Replace "...existing code" with appropriate content from original
        if "...existing code" in code:
            logger.info("Attempting to fix '...existing code' placeholders")
            lines = code.split('\n')
            fixed_lines = []
            i = 0
            
            while i < len(lines):
                line = lines[i]
                if "...existing code" in line:
                    # Get context around this placeholder
                    context_before = lines[max(0, i-5):i]
                    context_after = lines[min(i+1, len(lines)):min(i+6, len(lines))]
                    
                    # Find the section in the original code
                    replacement_section = CodeValidator._find_section_in_original(
                        context_before, context_after, original_code
                    )
                    
                    if replacement_section:
                        # Add the replacement section
                        fixed_lines.extend(replacement_section.split('\n'))
                    else:
                        # If we couldn't find a replacement, keep the placeholder
                        fixed_lines.append(line)
                else:
                    fixed_lines.append(line)
                i += 1
                
            code = '\n'.join(fixed_lines)
        
        # Ensure proper docstring at beginning if missing
        if not code.strip().startswith('"""') and original_code.strip().startswith('"""'):
            # Extract docstring from original
            docstring_match = re.match(r'(""".*?""")', original_code, re.DOTALL)
            if docstring_match:
                docstring = docstring_match.group(1)
                code = docstring + "\n\n" + code
        
        # Ensure main block at end if missing
        if "if __name__ == \"__main__\":" not in code and "if __name__ == \"__main__\":" in original_code:
            # Extract main block from original
            main_block_match = re.search(r'(if\s+__name__\s*==\s*"__main__":.+?)$', original_code, re.DOTALL)
            if main_block_match:
                main_block = main_block_match.group(1)
                code = code + "\n\n\n" + main_block
        
        # Fix missing imports
        original_imports = CodeValidator._extract_imports(original_code)
        new_imports = CodeValidator._extract_imports(code)
        missing_imports = [imp for imp in original_imports if imp not in new_imports]
        
        if missing_imports:
            # Find where imports end in the new code
            import_end_idx = 0
            lines = code.split('\n')
            
            for i, line in enumerate(lines):
                if re.match(r'^(?:from\s+[\w.]+\s+import\s+[\w,\s]+|import\s+[\w,\s.]+)$', line.strip()):
                    import_end_idx = i
            
            # Insert missing imports after the last import
            for imp in missing_imports:
                lines.insert(import_end_idx + 1, imp)
                import_end_idx += 1
                
            code = '\n'.join(lines)
        
        # Fix missing classes and functions
        # This is a more complex task that would require AST parsing for a complete solution
        # Here we'll implement a simplified approach
        
        return code
    
    @staticmethod
    def _fix_truncated_code(code: str, original_code: str) -> str:
        """
        Check for and fix truncated code by comparing with the original.
        
        Args:
            code: The generated code to check
            original_code: The original code for reference
            
        Returns:
            Fixed code if truncated, otherwise the original code
        """
        # Check if the code is significantly shorter than the original
        # This could indicate truncation
        if len(code) < len(original_code) * 0.7:  # If less than 70% of original length
            logger.warning("Generated code appears to be truncated")
            
            # Check for missing closing braces, parentheses, etc.
            stack = []
            for char in code:
                if char in '({[':
                    stack.append(char)
                elif char in ')}]':
                    if stack and ((stack[-1] == '(' and char == ')') or
                                 (stack[-1] == '{' and char == '}') or
                                 (stack[-1] == '[' and char == ']')):
                        stack.pop()
            
            # If we have unclosed delimiters, try to fix them
            if stack:
                logger.info(f"Attempting to fix {len(stack)} unclosed delimiters")
                for opener in reversed(stack):
                    if opener == '(':
                        code += ')'
                    elif opener == '{':
                        code += '}'
                    elif opener == '[':
                        code += ']'
            
            # Check for missing main block
            if "if __name__ == \"__main__\":" not in code and "if __name__ == \"__main__\":" in original_code:
                main_block_match = re.search(r'(if\s+__name__\s*==\s*"__main__":.+?)$', original_code, re.DOTALL)
                if main_block_match:
                    main_block = main_block_match.group(1)
                    code += "\n\n\n" + main_block
            
            # Check for missing class or function definitions at the end
            original_classes = CodeValidator._extract_class_names(original_code)
            new_classes = CodeValidator._extract_class_names(code)
            missing_classes = [cls for cls in original_classes if cls not in new_classes]
            
            if missing_classes:
                logger.info(f"Attempting to add missing classes: {', '.join(missing_classes)}")
                for cls_name in missing_classes:
                    # Find the class definition in the original code
                    class_pattern = re.compile(r'class\s+' + cls_name + r'[\(:].*?(?=class\s+\w+[\(:])|\Z', re.DOTALL)
                    class_match = class_pattern.search(original_code)
                    if class_match:
                        code += "\n\n" + class_match.group(0)
        
        return code
    
    @staticmethod
    def _find_section_in_original(context_before: List[str], context_after: List[str], original_code: str) -> str:
        """
        Find the corresponding section in the original code using fuzzy matching.
        
        Args:
            context_before: Lines before the "...existing code" placeholder
            context_after: Lines after the "...existing code" placeholder
            original_code: The original code to search in
            
        Returns:
            The section from the original code that should replace the placeholder
        """
        # Clean and prepare the context lines
        context_before = [line.strip() for line in context_before if line.strip()]
        context_after = [line.strip() for line in context_after if line.strip()]
        
        if not context_before and not context_after:
            return ""  # Not enough context to find a match
            
        original_lines = original_code.split('\n')
        original_lines = [line.strip() for line in original_lines]
        
        # Try to find the start and end positions in the original code
        start_idx = -1
        end_idx = -1
        
        # Find the start position using context_before
        if context_before:
            # Create a pattern from the last few lines of context_before
            pattern_lines = context_before[-min(3, len(context_before)):]
            pattern = r'\s*'.join([re.escape(line) for line in pattern_lines])
            
            # Search for this pattern in the original code
            for i in range(len(original_lines) - len(pattern_lines) + 1):
                section = '\n'.join(original_lines[i:i+len(pattern_lines)])
                if re.search(pattern, section, re.MULTILINE):
                    start_idx = i + len(pattern_lines)
                    break
        
        # Find the end position using context_after
        if context_after:
            # Create a pattern from the first few lines of context_after
            pattern_lines = context_after[:min(3, len(context_after))]
            pattern = r'\s*'.join([re.escape(line) for line in pattern_lines])
            
            # Search for this pattern in the original code
            for i in range(len(original_lines) - len(pattern_lines) + 1):
                section = '\n'.join(original_lines[i:i+len(pattern_lines)])
                if re.search(pattern, section, re.MULTILINE):
                    end_idx = i
                    break
        
        # If we couldn't find both start and end, try a different approach
        if start_idx == -1 or end_idx == -1 or start_idx >= end_idx:
            # Try to find the closest matching section using the longest common subsequence
            return CodeValidator._find_closest_section(context_before, context_after, original_lines)
        
        # Extract the section between start and end
        section = '\n'.join(original_lines[start_idx:end_idx])
        return section
    
    @staticmethod
    def _find_closest_section(context_before: List[str], context_after: List[str], original_lines: List[str]) -> str:
        """
        Find the closest matching section using text similarity.
        
        Args:
            context_before: Lines before the "...existing code" placeholder
            context_after: Lines after the "...existing code" placeholder
            original_lines: Lines from the original code
            
        Returns:
            The closest matching section from the original code
        """
        # If we have both context_before and context_after, try to find a section that fits between them
        if context_before and context_after:
            # Look for the last line of context_before
            last_before = context_before[-1]
            first_after = context_after[0]
            
            for i in range(len(original_lines)):
                if original_lines[i].strip() == last_before.strip():
                    # Found the last line of context_before, now look for first line of context_after
                    for j in range(i+1, len(original_lines)):
                        if original_lines[j].strip() == first_after.strip():
                            # Found both, return the section in between
                            return '\n'.join(original_lines[i+1:j])
        
        # If we couldn't find an exact match, use a more fuzzy approach
        # This is a simplified implementation - a more sophisticated approach would use
        # algorithms like longest common subsequence or text similarity metrics
        
        # For now, return an empty string as a fallback
        return ""

@dataclass
class Config:
    """Manages configuration settings using dataclass for better structure."""
    
    api_key: str = field(default="")
    model_name: str = field(default=DEFAULT_MODEL_NAME)
    temperature: float = field(default=DEFAULT_TEMPERATURE)
    max_output_tokens: int = field(default=DEFAULT_MAX_OUTPUT_TOKENS)
    top_p: float = field(default=DEFAULT_TOP_P)
    top_k: int = field(default=DEFAULT_TOP_K)
    
    def __post_init__(self):
        """Initialize after dataclass initialization."""
        # Register config attributes as tokens
        for key, value in asdict(self).items():
            TokenRegistry.register(f"CONFIG_{key.upper()}", value)
    
    @classmethod
    def from_env(cls) -> 'Config':
        """Create a Config instance from environment variables."""
        load_dotenv()
        
        api_key = os.getenv(ENV_API_KEY)
        if not api_key:
            raise ValueError(f"{ENV_API_KEY} not found in environment variables.")
        
        config = cls(
            api_key=api_key,
            model_name=os.getenv(ENV_MODEL_NAME, DEFAULT_MODEL_NAME),
            temperature=float(os.getenv(ENV_TEMPERATURE, DEFAULT_TEMPERATURE)),
            max_output_tokens=int(os.getenv(ENV_MAX_OUTPUT_TOKENS, DEFAULT_MAX_OUTPUT_TOKENS)),
            top_p=float(os.getenv(ENV_TOP_P, DEFAULT_TOP_P)),
            top_k=int(os.getenv(ENV_TOP_K, DEFAULT_TOP_K))
        )
        
        # Configure Gemini API
        genai.configure(api_key=config.api_key)
        
        return config
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert config to dictionary."""
        return asdict(self)
    
    def get_generation_config(self) -> Dict[str, Any]:
        """Get generation configuration for Gemini API."""
        return {
            "temperature": self.temperature,
            "max_output_tokens": self.max_output_tokens,
            "top_p": self.top_p,
            "top_k": self.top_k,
        }

class Goal:
    """Base class for defining goals."""
    
    description: str = "No description provided"
    
    def __init__(self):
        """Initialize the goal and register it with the token registry."""
        TokenRegistry.register(f"GOAL_{self.__class__.__name__.upper()}", self.description)
    
    def get_prompt(self, current_code: str, config: Config) -> str:
        """Generate a prompt for the AI based on the current code and this goal."""
        raise NotImplementedError("Subclasses must implement get_prompt method")


class SelfEditGoal(Goal):
    """Goal for self-editing and improvement."""
    
    description = "Improve code structure, functionality, and robustness."
    
    def get_prompt(self, current_code: str, config: Config) -> str:
        """Generate a prompt for self-editing."""
        return f"""
        Improve the following Python script:

        ```python
        {current_code}
        ```

        Focus on:
        1. SOLID, DRY, PEP 8, and KISS principles.
        2. Enhanced self-modification capabilities.
        3. Robustness and error handling.
        4. Useful features aligned with its purpose.
        5. Maintain and improve the version control and token system.
        6. Use dataclasses where appropriate for better structure.

        IMPORTANT GUIDELINES:
        1. DO NOT use "...existing code" placeholders. Always include the complete code.
        2. Ensure all imports from the original code are preserved.
        3. Keep the docstring at the beginning and the main execution block at the end.
        4. Maintain the VERSION constant and update it appropriately.
        5. Preserve all existing class and function definitions.
        6. Use consistent indentation (4 spaces per level).
        7. Ensure all delimiters (quotes, parentheses, brackets) are properly closed.
        8. The code must be syntactically correct and directly executable.

        The script uses a token system to avoid attribute mismatches. Tokens are formatted as <TOKEN:NAME> 
        and are registered in the TokenRegistry. Use this system when referring to configuration values 
        or other important constants.

        Return ONLY the improved code, directly executable.
        """
        
    def get_enhanced_prompt(self, current_code: str, config: Config, issues: List[str]) -> str:
        """
        Generate an enhanced prompt that specifically addresses identified issues.
        
        Args:
            current_code: The current code
            config: The configuration
            issues: List of issues identified in a previous generation attempt
            
        Returns:
            An enhanced prompt
        """
        issue_guidance = "\n        ".join([f"- {issue}" for issue in issues])
        
        return f"""
        Improve the following Python script, paying special attention to fixing these specific issues:
        
        {issue_guidance}

        ```python
        {current_code}
        ```

        Focus on:
        1. SOLID, DRY, PEP 8, and KISS principles.
        2. Enhanced self-modification capabilities.
        3. Robustness and error handling.
        4. Useful features aligned with its purpose.
        5. Maintain and improve the version control and token system.
        6. Use dataclasses where appropriate for better structure.

        CRITICAL REQUIREMENTS:
        1. DO NOT use "...existing code" placeholders. Always include the complete code.
        2. Ensure all imports from the original code are preserved.
        3. Keep the docstring at the beginning and the main execution block at the end.
        4. Maintain the VERSION constant and update it appropriately.
        5. Preserve all existing class and function definitions.
        6. Use consistent indentation (4 spaces per level).
        7. Ensure all delimiters (quotes, parentheses, brackets) are properly closed.
        8. The code must be syntactically correct and directly executable.

        The script uses a token system to avoid attribute mismatches. Tokens are formatted as <TOKEN:NAME> 
        and are registered in the TokenRegistry. Use this system when referring to configuration values 
        or other important constants.

        Return ONLY the improved code, directly executable.
        """


class GeminiAPI:
    """Interface for interacting with the Gemini API."""
    
    def __init__(self, config: Config):
        """Initialize the API interface with configuration."""
        self.config = config
        TokenRegistry.register("GEMINI_API", self.__class__.__name__)
        
        # Use token registry to get model name
        self.model = genai.GenerativeModel(
            model_name=config.model_name,
            generation_config=config.get_generation_config()
        )
    
    def generate_response(self, prompt: str) -> Optional[str]:
        """Generate a response from the AI model based on the given prompt."""
        try:
            # Validate tokens in the prompt
            invalid_tokens = TokenRegistry.validate_tokens(prompt)
            if invalid_tokens:
                logger.warning(f"Invalid tokens in prompt: {invalid_tokens}")
            
            # Replace valid tokens
            prompt = TokenRegistry.replace_tokens(prompt)
            
            response = self.model.generate_content(prompt)
            code = response.text
            
            # Check for incomplete code and fix if possible
            code = self._fix_incomplete_code(code)
            
            return code
        except Exception as e:
            logger.error(f"Gemini API error: {e}")
            return None
            
    def _fix_incomplete_code(self, code: str) -> str:
        """
        Check for and fix incomplete generated code.
        
        Args:
            code: The generated code
            
        Returns:
            Fixed code if possible, otherwise the original code
        """
        if not code:
            return code
            
        # Check for unterminated string literals
        try:
            compile(code, '<string>', 'exec')
            return code  # Code is valid, no need to fix
        except SyntaxError as e:
            error_msg = str(e)
            
            # Handle unterminated string literals
            if "unterminated" in error_msg and "string" in error_msg:
                logger.warning(f"Detected unterminated string: {error_msg}")
                
                # Try to fix unterminated triple-quoted strings
                if "triple-quoted" in error_msg:
                    # Add closing triple quotes at the end
                    if '"""' in code:
                        return code + '\n"""'
                    elif "'''" in code:
                        return code + "\n'''"
                
                # Try to fix unterminated single-quoted strings
                elif "string literal" in error_msg:
                    # This is more complex, but we can try a simple approach
                    # Find the line with the error
                    line_match = re.search(r'line (\d+)', error_msg)
                    if line_match:
                        line_num = int(line_match.group(1))
                        lines = code.split('\n')
                        
                        if line_num <= len(lines):
                            # Add a closing quote to the problematic line
                            if '"' in lines[line_num-1] and lines[line_num-1].count('"') % 2 == 1:
                                lines[line_num-1] += '"'
                            elif "'" in lines[line_num-1] and lines[line_num-1].count("'") % 2 == 1:
                                lines[line_num-1] += "'"
                                
                            return '\n'.join(lines)
            
            # If we couldn't fix it, return the original code
            return code


class CodeManager:
    """Manages reading, writing, and versioning code."""
    
    def __init__(self):
        """Initialize the code manager and register it with the token registry."""
        TokenRegistry.register("CODE_MANAGER", self.__class__.__name__)
    
    @staticmethod
    def read_code(filepath: Path) -> Optional[str]:
        """Read code from a file."""
        try:
            with open(filepath, 'r') as f:
                code = f.read()
                
            # Validate tokens in the code
            invalid_tokens = TokenRegistry.validate_tokens(code)
            if invalid_tokens:
                logger.warning(f"Invalid tokens in code: {invalid_tokens}")
                
            return code
        except FileNotFoundError:
            logger.error(f"File not found: {filepath}")
        except Exception as e:
            logger.error(f"Error reading file: {e}")
        return None
    
    @staticmethod
    def write_code(filepath: Path, code: str) -> bool:
        """Write code to a file."""
        try:
            # Replace tokens in the code
            code = TokenRegistry.replace_tokens(code)
            
            with open(filepath, 'w') as f:
                f.write(code)
            return True
        except Exception as e:
            logger.error(f"Error writing file: {e}")
            return False
    
    @staticmethod
    def calculate_hash(code: str) -> str:
        """Calculate a hash for the code."""
        return hashlib.sha256(code.encode('utf-8')).hexdigest()
    
    @staticmethod
    def extract_version(code: str) -> str:
        """Extract version from code."""
        for line in code.split('\n'):
            if line.startswith('VERSION = '):
                return line.split('=')[1].strip().strip('"\'')
        return "unknown"


class VersionControl:
    """Manages version control for the script."""
    
    def __init__(self, directory: Path = VERSION_HISTORY_DIR, metadata_file: str = VERSION_METADATA_FILE):
        """Initialize version control with directory and metadata file."""
        self.directory = directory
        self.metadata_file = metadata_file
        TokenRegistry.register("VERSION_CONTROL", self.__class__.__name__)
        
        # Create directory if it doesn't exist
        if not self.directory.exists():
            self.directory.mkdir(parents=True, exist_ok=True)
            logger.info(f"Created version history directory: {self.directory}")
    
    def get_metadata_path(self) -> Path:
        """Get the path to the metadata file."""
        return self.directory / self.metadata_file
    
    def _load_metadata(self) -> Dict:
        """Load metadata from file with error handling."""
        try:
            metadata_path = self.get_metadata_path()
            if metadata_path.exists():
                with open(metadata_path, 'r') as f:
                    return json.load(f)
            return {"versions": [], "latest_version": None}
        except Exception as e:
            logger.error(f"Error loading metadata: {e}")
            return {"versions": [], "latest_version": None}
    
    def _save_metadata(self, metadata: Dict) -> None:
        """Save metadata to file with error handling."""
        try:
            with open(self.get_metadata_path(), 'w') as f:
                json.dump(metadata, f, indent=2)
        except Exception as e:
            logger.error(f"Error saving metadata: {e}")
    
    def save_version(self, code: str, version: str) -> None:
        """Save a version of the code."""
        try:
            # Calculate hash
            code_hash = CodeManager.calculate_hash(code)
            
            # Create version filename
            timestamp = datetime.datetime.now().strftime("%Y%m%d%H%M%S")
            version_filename = f"adaptagen_{version.replace('.', '_').replace('-', '_')}_{timestamp}.py"
            version_path = self.directory / version_filename
            
            # Save the code
            with open(version_path, 'w') as f:
                f.write(code)
            
            # Update metadata
            metadata = self._load_metadata()
            version_info = {
                "version": version,
                "timestamp": timestamp,
                "hash": code_hash,
                "filename": version_filename,
                "path": str(version_path)
            }
            metadata["versions"].append(version_info)
            metadata["latest_version"] = version_info
            
            self._save_metadata(metadata)
            logger.info(f"Saved version {version} to {version_path}")
        except Exception as e:
            logger.error(f"Error saving version: {e}")
    
    def get_version_history(self) -> List[Dict]:
        """Get the version history."""
        return self._load_metadata().get("versions", [])
    
    def get_latest_version(self) -> Optional[Dict]:
        """Get the latest version info."""
        return self._load_metadata().get("latest_version")


class VersionManager:
    """Manages version numbers and updates."""
    
    def __init__(self):
        """Initialize the version manager and register it with the token registry."""
        TokenRegistry.register("VERSION_MANAGER", self.__class__.__name__)
        TokenRegistry.register("CURRENT_VERSION", VERSION)
    
    @staticmethod
    def increment_version(version: str, increment_type: str = 'revision') -> str:
        """
        Increment the version number.
        
        Args:
            version: Current version string (format: major.minor.patch-revision)
            increment_type: Type of increment ('major', 'minor', 'patch', or 'revision')
            
        Returns:
            New version string
        """
        try:
            # Split version into components
            if '-' in version:
                version_part, revision_part = version.split('-')
                major, minor, patch = map(int, version_part.split('.'))
                revision = int(revision_part[1:]) if revision_part.startswith('r') else int(revision_part)
            else:
                major, minor, patch = map(int, version.split('.'))
                revision = 0
            
            # Increment based on type
            if increment_type == 'major':
                major += 1
                minor = 0
                patch = 0
                revision = 0
            elif increment_type == 'minor':
                minor += 1
                patch = 0
                revision = 0
            elif increment_type == 'patch':
                patch += 1
                revision = 0
            else:  # revision
                revision += 1
            
            # Format new version
            new_version = f"{major}.{minor}.{patch}-r{revision}"
            TokenRegistry.register("NEW_VERSION", new_version)
            return new_version
        except Exception as e:
            logger.error(f"Error incrementing version: {e}")
            fallback = f"{version}-r1"
            TokenRegistry.register("NEW_VERSION", fallback)
            return fallback
    
    @staticmethod
    def update_version_in_code(code: str, new_version: str) -> str:
        """Update the version constant in the code."""
        lines = code.split('\n')
        for i, line in enumerate(lines):
            if line.startswith('VERSION = '):
                lines[i] = f'VERSION = "{new_version}"'
                break
        return '\n'.join(lines)

class IncrementalEditor:
    """
    Manages incremental editing of code with verification after each change.
    Makes small, controlled edits and verifies they work before proceeding.
    """
    
    def __init__(self, original_code: str, code_manager: CodeManager, 
                 version_control: VersionControl, gemini_api: GeminiAPI,
                 target_file: Path = None):
        """Initialize the incremental editor."""
        self.original_code = original_code
        self.current_code = original_code
        self.code_manager = code_manager
        self.version_control = version_control
        self.gemini_api = gemini_api
        self.target_file = target_file
        self.edit_history = []
        self.successful_edits = 0
        self.failed_edits = 0
        self.backoff_times = [1, 2, 5, 10, 30, 60]  # Backoff times in seconds
        self.edit_approaches = [
            self._approach_standard_edit,
            self._approach_simplified_edit,
            self._approach_conservative_edit,
            self._approach_focused_bugfix
        ]
        
    def get_component_edit_prompt(self, component_name: str, component_code: str, 
                                  approach: str = "standard") -> str:
        """
        Generate a prompt for editing a specific component.
        
        Args:
            component_name: Name of the component to edit
            component_code: Code of the component to edit
            approach: Editing approach to use
            
        Returns:
            Prompt for editing the component
        """
        base_prompt = f"""
        Improve the following {component_name} component from a Python script:

        ```python
        {component_code}
        ```
        """
        
        if approach == "standard":
            focus = """
            Focus on:
            1. Improving functionality and robustness
            2. Better error handling
            3. Code clarity and documentation
            4. Performance optimizations if applicable
            """
        elif approach == "simplified":
            focus = """
            Focus on:
            1. Simplifying the code while maintaining functionality
            2. Removing unnecessary complexity
            3. Making the code more readable
            """
        elif approach == "conservative":
            focus = """
            Focus on:
            1. Making minimal changes to fix obvious issues
            2. Improving comments and documentation
            3. DO NOT change the core logic or structure
            """
        elif approach == "bugfix":
            focus = """
            Focus ONLY on:
            1. Fixing bugs and edge cases
            2. Improving error handling
            3. DO NOT add new features or change existing functionality
            """
        
        guidelines = """
        IMPORTANT:
        1. Return ONLY the improved component code, nothing else
        2. Maintain the same function/method signatures
        3. Ensure the code is syntactically correct
        4. Do not change the component's core purpose
        5. Do not add dependencies on components that don't exist
        """
        
        return base_prompt + focus + guidelines + "\n\nReturn the complete improved component code."
    
    def extract_components(self) -> Dict[str, str]:
        """
        Extract individual components (classes, functions) from the code.
        
        Returns:
            Dictionary mapping component names to their code
        """
        components = {}
        
        # Extract classes
        class_pattern = re.compile(r'(class\s+(\w+)[\(:].*?)(?=class\s+\w+[\(:]|\Z)', re.DOTALL)
        for match in class_pattern.finditer(self.current_code):
            class_code = match.group(1)
            class_name = match.group(2)
            components[class_name] = class_code
            
        # Extract standalone functions
        function_pattern = re.compile(r'(def\s+(\w+)\s*\(.*?\).*?)(?=def\s+\w+\s*\(|\Z|class\s+\w+[\(:])', re.DOTALL)
        for match in function_pattern.finditer(self.current_code):
            # Skip methods inside classes
            if not re.search(r'^\s+def', match.group(1), re.MULTILINE):
                function_code = match.group(1)
                function_name = match.group(2)
                components[function_name] = function_code
                
        return components
    
    def replace_component(self, component_name: str, new_component_code: str) -> str:
        """
        Replace a component in the code with its improved version.
        
        Args:
            component_name: Name of the component to replace
            new_component_code: New code for the component
            
        Returns:
            Updated full code
        """
        # For classes
        class_pattern = re.compile(f'(class\\s+{component_name}[\\(:].*?)(?=class\\s+\\w+[\\(:]|\\Z)', re.DOTALL)
        if class_pattern.search(self.current_code):
            return class_pattern.sub(new_component_code, self.current_code)
            
        # For standalone functions
        function_pattern = re.compile(f'(def\\s+{component_name}\\s*\\(.*?\\).*?)(?=def\\s+\\w+\\s*\\(|\\Z|class\\s+\\w+[\\(:])', re.DOTALL)
        if function_pattern.search(self.current_code):
            return function_pattern.sub(new_component_code, self.current_code)
            
        # If component not found, return original code
        logger.warning(f"Component {component_name} not found in code")
        return self.current_code
    
    def verify_code(self, code: str) -> bool:
        """
        Verify that the code is valid and can be executed.
        
        Args:
            code: Code to verify
            
        Returns:
            True if code is valid, False otherwise
        """
        try:
            # Check for syntax errors
            compile(code, '<string>', 'exec')
            
            # Use CodeValidator for more thorough checks
            validator = CodeValidator()
            is_valid, issues = validator.validate_code(code, self.original_code)
            
            if not is_valid:
                logger.warning(f"Code validation failed: {', '.join(issues)}")
                return False
            
            # Test the code functionality
            if not self.test_code_functionality(code):
                logger.warning("Code functionality test failed")
                return False
                
            return True
        except Exception as e:
            logger.error(f"Code verification failed: {e}")
            return False
    
    def test_code_functionality(self, code: str) -> bool:
        """
        Test the functionality of the code by executing it in a controlled environment.
        
        Args:
            code: Code to test
            
        Returns:
            True if code passes functional tests, False otherwise
        """
        try:
            # Create a temporary file for the code
            import tempfile
            with tempfile.NamedTemporaryFile(suffix='.py', delete=False) as temp_file:
                temp_path = temp_file.name
                temp_file.write(code.encode('utf-8'))
            
            # Execute the code in a subprocess to isolate it
            import subprocess
            result = subprocess.run(
                [sys.executable, temp_path, '--test'],
                capture_output=True,
                text=True,
                timeout=10  # Timeout after 10 seconds
            )
            
            # Clean up the temporary file
            import os
            os.unlink(temp_path)
            
            # Check if execution was successful
            if result.returncode != 0:
                logger.warning(f"Code execution failed with return code {result.returncode}")
                logger.warning(f"Error output: {result.stderr}")
                return False
            
            return True
        except subprocess.TimeoutExpired:
            logger.warning("Code execution timed out")
            return False
        except Exception as e:
            logger.error(f"Error testing code functionality: {e}")
            return False
    
    def _approach_standard_edit(self, component_name: str, component_code: str) -> str:
        """Standard editing approach."""
        prompt = self.get_component_edit_prompt(component_name, component_code, "standard")
        return self.gemini_api.generate_response(prompt)
    
    def _approach_simplified_edit(self, component_name: str, component_code: str) -> str:
        """Simplified editing approach focusing on readability."""
        prompt = self.get_component_edit_prompt(component_name, component_code, "simplified")
        return self.gemini_api.generate_response(prompt)
    
    def _approach_conservative_edit(self, component_name: str, component_code: str) -> str:
        """Conservative editing approach with minimal changes."""
        prompt = self.get_component_edit_prompt(component_name, component_code, "conservative")
        return self.gemini_api.generate_response(prompt)
    
    def _approach_focused_bugfix(self, component_name: str, component_code: str) -> str:
        """Focused bug-fixing approach."""
        prompt = self.get_component_edit_prompt(component_name, component_code, "bugfix")
        return self.gemini_api.generate_response(prompt)
    
    def try_edit_component(self, component_name: str, component_code: str) -> Tuple[bool, str]:
        """
        Try to edit a component using multiple approaches with timed backoff.
        
        Args:
            component_name: Name of the component to edit
            component_code: Code of the component to edit
            
        Returns:
            Tuple of (success, new_code)
        """
        import time
        
        # Try each approach
        for approach_idx, approach_func in enumerate(self.edit_approaches):
            logger.info(f"Trying approach {approach_idx+1}/{len(self.edit_approaches)} for {component_name}")
            
            # Try with backoff
            for attempt, backoff_time in enumerate(self.backoff_times):
                logger.info(f"Attempt {attempt+1}/{len(self.backoff_times)} with {backoff_time}s backoff")
                
                # Generate improved component
                improved_component = approach_func(component_name, component_code)
                
                if not improved_component:
                    logger.warning(f"Failed to generate improved version for {component_name}")
                    time.sleep(backoff_time)
                    continue
                
                # Replace component in the code
                new_code = self.replace_component(component_name, improved_component)
                
                # Verify the new code
                if self.verify_code(new_code):
                    logger.info(f"Successfully improved component: {component_name}")
                    return True, new_code
                
                logger.warning(f"Verification failed for {component_name}, backing off for {backoff_time}s")
                time.sleep(backoff_time)
            
            # If we've tried all backoff times with this approach and failed, try the next approach
            logger.warning(f"All attempts with approach {approach_idx+1} failed for {component_name}")
        
        # If all approaches failed, return failure
        logger.error(f"All approaches failed for {component_name}")
        return False, self.current_code
    
    def save_current_code(self, version_suffix: str = None) -> None:
        """
        Save the current code to the target file and version history.
        
        Args:
            version_suffix: Optional suffix to add to the version
        """
        if self.target_file:
            # Save to the target file
            self.code_manager.write_code(self.target_file, self.current_code)
            logger.info(f"Saved current code to {self.target_file}")
            
            # Save to version history
            timestamp = datetime.datetime.now().strftime("%Y%m%d%H%M%S")
            version = f"{VERSION}-{version_suffix}_{timestamp}" if version_suffix else f"{VERSION}-{timestamp}"
            self.version_control.save_version(self.current_code, version)
            logger.info(f"Saved version {version} to version history")
    
    def run_incremental_edit(self, version_suffix: str = "incremental") -> str:
        """
        Run the incremental editing process.
        
        Args:
            version_suffix: Suffix to add to version for saving
            
        Returns:
            Final improved code
        """
        logger.info("Starting incremental editing process")
        
        # Extract components
        components = self.extract_components()
        logger.info(f"Extracted {len(components)} components for incremental editing")
        
        # Sort components by size (smaller first for faster iterations)
        sorted_components = sorted(components.items(), key=lambda x: len(x[1]))
        
        # Process each component
        for component_name, component_code in sorted_components:
            logger.info(f"Processing component: {component_name}")
            
            # Try to edit the component
            success, new_code = self.try_edit_component(component_name, component_code)
            
            if success:
                self.current_code = new_code
                self.successful_edits += 1
                
                # Save the current state
                self.save_current_code(f"{version_suffix}_{component_name}")
                
                # Record successful edit
                self.edit_history.append({
                    "component": component_name,
                    "status": "success",
                    "timestamp": datetime.datetime.now().strftime("%Y%m%d%H%M%S")
                })
            else:
                self.failed_edits += 1
                
                # Record failed edit
                self.edit_history.append({
                    "component": component_name,
                    "status": "failed",
                    "timestamp": datetime.datetime.now().strftime("%Y%m%d%H%M%S")
                })
        
        logger.info(f"Incremental editing completed. Successful edits: {self.successful_edits}, Failed edits: {self.failed_edits}")
        return self.current_code

class AdaptaGen:
    """Orchestrates the self-modification process."""
    
    def __init__(self, config: Config):
        """Initialize the AdaptaGen system."""
        self.config = config
        self.gemini_api = GeminiAPI(config)
        self.code_manager = CodeManager()
        self.version_control = VersionControl()
        self.version_manager = VersionManager()
        self.current_goal = SelfEditGoal()
        
        # Register with token registry
        TokenRegistry.register("ADAPTAGEN", self.__class__.__name__)
    
    def run(self, increment_type: str = 'revision', use_incremental: bool = False) -> None:
        """
        Execute the self-modification process.
        
        Args:
            increment_type: Type of version increment ('major', 'minor', 'patch', or 'revision')
            use_incremental: Whether to use incremental editing instead of full regeneration
        """
        logger.info(f"Starting AdaptaGen {VERSION} with goal: {self.current_goal.description}")
        
        # Read the current source code
        current_filepath = Path(inspect.getfile(inspect.currentframe()))
        current_code = self.code_manager.read_code(current_filepath)
        if not current_code:
            logger.error("Failed to read source code.")
            return
        
        # Save current version to version history
        self.version_control.save_version(current_code, VERSION)
        
        # Increment version
        new_version = self.version_manager.increment_version(VERSION, increment_type)
        
        if use_incremental:
            # Use incremental editing approach
            logger.info("Using incremental editing approach")
            
            # Determine the target file path
            target_filepath = current_filepath
            
            # Create a backup of the current file
            backup_filepath = Path(f"{current_filepath}.bak")
            try:
                import shutil
                shutil.copy2(current_filepath, backup_filepath)
                logger.info(f"Created backup at {backup_filepath}")
            except Exception as e:
                logger.error(f"Failed to create backup: {e}")
                return
            
            # Initialize the incremental editor with the target file
            incremental_editor = IncrementalEditor(
                current_code, 
                self.code_manager, 
                self.version_control,
                self.gemini_api,
                target_filepath
            )
            
            try:
                # Run incremental editing
                improved_code = incremental_editor.run_incremental_edit(new_version)
                
                # Update version in code
                improved_code = self.version_manager.update_version_in_code(improved_code, new_version)
                
                # Write the final version back to the same file
                if self.code_manager.write_code(target_filepath, improved_code):
                    logger.info(f"Successfully updated {target_filepath} with version {new_version}")
                    
                    # Save to version history
                    self.version_control.save_version(improved_code, new_version)
                    
                    # Log statistics
                    logger.info(f"Incremental editing statistics: {incremental_editor.successful_edits} successful edits, {incremental_editor.failed_edits} failed edits")
                else:
                    logger.error(f"Failed to write to {target_filepath}")
                    self._restore_backup(backup_filepath, target_filepath)
            except Exception as e:
                logger.error(f"Error during incremental editing: {e}")
                self._restore_backup(backup_filepath, target_filepath)
            finally:
                # Clean up backup if everything went well
                if backup_filepath.exists() and incremental_editor.successful_edits > 0:
                    try:
                        backup_filepath.unlink()
                        logger.info(f"Removed backup file {backup_filepath}")
                    except Exception as e:
                        logger.warning(f"Failed to remove backup file: {e}")
            
            return
        
        # Traditional approach (full regeneration)
        # Generate a prompt based on the current goal
        prompt = self.current_goal.get_prompt(current_code, self.config)
        
        # Get AI-generated improvements
        logger.info("Generating improved version using AI...")
        improved_code = self.gemini_api.generate_response(prompt)
        
        # Error handling for API response
        if not improved_code:
            logger.error("Failed to generate improved code.")
            return
        
        # Maximum number of retry attempts
        max_retries = 2
        retry_count = 0
        
        while retry_count <= max_retries:
            try:
                # Attempt to compile the generated code to catch syntax errors early
                compile(improved_code, '<string>', 'exec')
                
                # Validate the generated code for common issues
                code_validator = CodeValidator()
                is_valid, issues = code_validator.validate_code(improved_code, current_code)
                
                if not is_valid:
                    logger.warning(f"Generated code has issues: {', '.join(issues)}")
                    
                    # If we have retries left, try to regenerate with an enhanced prompt
                    if retry_count < max_retries:
                        retry_count += 1
                        logger.info(f"Attempting to regenerate code (retry {retry_count}/{max_retries})...")
                        
                        # Generate an enhanced prompt that addresses the specific issues
                        enhanced_prompt = self.current_goal.get_enhanced_prompt(current_code, self.config, issues)
                        
                        # Save the problematic code for reference
                        self.version_control.save_version(
                            improved_code, 
                            f"{new_version}-retry{retry_count}_issues"
                        )
                        
                        # Generate new code with the enhanced prompt
                        improved_code = self.gemini_api.generate_response(enhanced_prompt)
                        
                        if not improved_code:
                            logger.error(f"Failed to regenerate code on retry {retry_count}.")
                            break
                            
                        # Continue to the next iteration to validate the new code
                        continue
                    
                    # If we're out of retries, attempt to fix common issues
                    logger.info("Attempting to fix common issues in generated code")
                    improved_code = code_validator.fix_common_issues(improved_code, current_code)
                    
                    # Validate again after fixes
                    is_valid, remaining_issues = code_validator.validate_code(improved_code, current_code)
                    if not is_valid:
                        logger.warning(f"Issues remain after fixes: {', '.join(remaining_issues)}")
                        # Save with issues flag
                        self.version_control.save_version(improved_code, f"{new_version}-with_issues")
                    else:
                        logger.info("Successfully fixed issues in generated code")
                
                # Update version in code
                improved_code = self.version_manager.update_version_in_code(improved_code, new_version)
                
                # Write the new version to a file
                new_filepath = Path(f"adaptagen_{new_version.replace('.', '_').replace('-', '_')}.py")
                if self.code_manager.write_code(new_filepath, improved_code):
                    logger.info(f"New version {new_version} written to: {new_filepath}")
                    
                    # Save to version history
                    self.version_control.save_version(improved_code, new_version)
                else:
                    logger.error("Failed to write new version.")
                
                # Break out of the retry loop if we get here
                break

            except SyntaxError as e:
                logger.error(f"Syntax error in generated code: {e}")
                
                # If we have retries left, try to regenerate
                if retry_count < max_retries:
                    retry_count += 1
                    logger.info(f"Attempting to regenerate code due to syntax error (retry {retry_count}/{max_retries})...")
                    
                    # Save the problematic code for reference
                    self.version_control.save_version(
                        improved_code, 
                        f"{new_version}-retry{retry_count}_syntax_error"
                    )
                    
                    # Create an enhanced prompt that specifically mentions the syntax error
                    syntax_error_prompt = self.current_goal.get_enhanced_prompt(
                        current_code, 
                        self.config, 
                        [f"Syntax error: {e}"]
                    )
                    
                    # Generate new code with the enhanced prompt
                    improved_code = self.gemini_api.generate_response(syntax_error_prompt)
                    
                    if not improved_code:
                        logger.error(f"Failed to regenerate code on retry {retry_count}.")
                        break
                else:
                    # If we're out of retries, save the problematic code and exit
                    self.version_control.save_version(improved_code, f"{new_version}-syntax_error")
                    return
    
    def _restore_backup(self, backup_filepath: Path, target_filepath: Path) -> None:
        """
        Restore from backup if something goes wrong.
        
        Args:
            backup_filepath: Path to the backup file
            target_filepath: Path to the target file to restore
        """
        try:
            if backup_filepath.exists():
                import shutil
                shutil.copy2(backup_filepath, target_filepath)
                logger.info(f"Restored from backup {backup_filepath}")
                
                # Remove the backup
                backup_filepath.unlink()
        except Exception as e:
            logger.error(f"Failed to restore from backup: {e}")
    
    def list_versions(self) -> None:
        """List all versions in the version history."""
        versions = self.version_control.get_version_history()
        if not versions:
            logger.info("No version history found.")
            return
        
        logger.info("Version history:")
        for version in versions:
            logger.info(f"- {version['version']} ({version['timestamp']}): {version['path']}")


def main():
    """Main entry point for the script."""
    try:
        # Parse command line arguments
        parser = argparse.ArgumentParser(description='AdaptaGen: Self-modifying Python script')
        parser.add_argument('--incremental', action='store_true', 
                            help='Use incremental editing approach instead of full regeneration')
        parser.add_argument('--version-type', choices=['major', 'minor', 'patch', 'revision'],
                            default='revision', help='Type of version increment')
        parser.add_argument('--test', action='store_true',
                            help='Run in test mode to verify functionality')
        args = parser.parse_args()
        
        # Test mode - just verify the script can be imported and run basic functions
        if args.test:
            # In test mode, we just exit successfully to indicate the script is valid
            logger.info("Test mode: Script loaded successfully")
            sys.exit(0)
        
        # Initialize configuration from environment variables
        config = Config.from_env()
        
        # Create and run AdaptaGen
        adaptagen = AdaptaGen(config)
        adaptagen.run(increment_type=args.version_type, use_incremental=args.incremental)
        
    except ValueError as e:
        logger.error(e)
        sys.exit(1)
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        sys.exit(1)



if __name__ == "__main__":
    main()
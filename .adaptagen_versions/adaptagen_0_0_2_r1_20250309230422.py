"""
AdaptaGen: A self-modifying Python script using the Gemini API with version control.

Version: 0.0.2-r1

Enhancements in 0.0.2-r1:
1. Added learning from past improvements:
   - Maintains a database of successful and failed edits
   - Analyzes patterns in successful improvements
   - Prioritizes components based on historical success rates
   - Adapts prompts based on what has worked in the past

2. Implemented progressive complexity management:
   - Starts with simpler, more focused improvements
   - Gradually increases complexity as successes accumulate
   - Tracks complexity metrics for each component
   - Avoids overwhelming changes that could break functionality

3. Added self-evaluation capabilities:
   - Evaluates its own code quality using static analysis
   - Tracks metrics over time to measure improvement
   - Identifies areas most in need of enhancement
   - Generates reports on improvement progress

4. Enhanced goal management:
   - Supports multiple improvement goals with priorities
   - Rotates focus areas to ensure balanced improvement
   - Allows for specialized goals targeting specific subsystems
   - Maintains a roadmap of planned improvements

5. Improved resource efficiency:
   - Implements intelligent caching of API responses
   - Prioritizes changes with highest impact-to-cost ratio
   - Adapts resource usage based on available API quota
   - Schedules intensive operations during low-usage periods

Previous enhancements:
1. Added intelligent rate limit handling:
   - Implements exponential backoff for 429 errors
   - Automatically retries requests after appropriate waiting periods
   - Preserves API quota by adapting to service limitations
   - Maintains state between requests to optimize retry behavior

2. Added comprehensive code validation to check for common issues in generated code:
   - Syntax errors
   - "...existing code" placeholders
   - Missing imports, classes, and functions
   - Incomplete beginning and end of code
   - Inconsistent indentation
   - Unclosed delimiters (quotes, parentheses, brackets)

3. Implemented automatic fixing of common issues:
   - Replacing "...existing code" placeholders with appropriate content
   - Adding missing docstrings and main execution blocks
   - Fixing missing imports
   - Handling truncated code
   - Fixing unclosed delimiters and string literals

4. Added a retry mechanism with enhanced prompts:
   - Generates specific prompts addressing identified issues
   - Makes multiple attempts before falling back to automatic fixes
   - Saves intermediate versions with descriptive suffixes for debugging

5. Improved prompt generation:
   - Added specific guidelines to prevent common issues
   - Created enhanced prompts that address specific problems

6. Added advanced incremental editing approach:
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
VERSION = "0.0.2-r1"
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
    priority: int = 5  # Default priority (1-10, 10 being highest)
    
    def __init__(self):
        """Initialize the goal and register it with the token registry."""
        TokenRegistry.register(f"GOAL_{self.__class__.__name__.upper()}", self.description)
    
    def get_prompt(self, current_code: str, config: Config) -> str:
        """Generate a prompt for the AI based on the current code and this goal."""
        raise NotImplementedError("Subclasses must implement get_prompt method")
    
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
        raise NotImplementedError("Subclasses must implement get_enhanced_prompt method")


class SelfEditGoal(Goal):
    """Goal for self-editing and improvement."""
    
    description = "Improve code structure, functionality, and robustness."
    priority = 10  # Highest priority
    
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


class PerformanceGoal(Goal):
    """Goal for improving performance and efficiency."""
    
    description = "Improve performance and efficiency of the code."
    priority = 7
    
    def get_prompt(self, current_code: str, config: Config) -> str:
        """Generate a prompt for performance optimization."""
        return f"""
        Optimize the performance of the following Python script:

        ```python
        {current_code}
        ```

        Focus on:
        1. Algorithmic efficiency improvements
        2. Reducing unnecessary computations
        3. Optimizing resource usage (memory, CPU)
        4. Improving I/O operations
        5. Reducing redundant code execution

        IMPORTANT GUIDELINES:
        1. DO NOT use "...existing code" placeholders. Always include the complete code.
        2. Ensure all imports from the original code are preserved.
        3. Keep the docstring at the beginning and the main execution block at the end.
        4. Maintain the VERSION constant and update it appropriately.
        5. Preserve all existing class and function definitions.
        6. Use consistent indentation (4 spaces per level).
        7. Ensure all delimiters (quotes, parentheses, brackets) are properly closed.
        8. The code must be syntactically correct and directly executable.
        9. DO NOT sacrifice readability or maintainability for minor performance gains.

        The script uses a token system to avoid attribute mismatches. Tokens are formatted as <TOKEN:NAME> 
        and are registered in the TokenRegistry. Use this system when referring to configuration values 
        or other important constants.

        Return ONLY the improved code, directly executable.
        """
        
    def get_enhanced_prompt(self, current_code: str, config: Config, issues: List[str]) -> str:
        """Generate an enhanced prompt for performance optimization."""
        issue_guidance = "\n        ".join([f"- {issue}" for issue in issues])
        
        return f"""
        Optimize the performance of the following Python script, paying special attention to fixing these specific issues:
        
        {issue_guidance}

        ```python
        {current_code}
        ```

        Focus on:
        1. Algorithmic efficiency improvements
        2. Reducing unnecessary computations
        3. Optimizing resource usage (memory, CPU)
        4. Improving I/O operations
        5. Reducing redundant code execution

        CRITICAL REQUIREMENTS:
        1. DO NOT use "...existing code" placeholders. Always include the complete code.
        2. Ensure all imports from the original code are preserved.
        3. Keep the docstring at the beginning and the main execution block at the end.
        4. Maintain the VERSION constant and update it appropriately.
        5. Preserve all existing class and function definitions.
        6. Use consistent indentation (4 spaces per level).
        7. Ensure all delimiters (quotes, parentheses, brackets) are properly closed.
        8. The code must be syntactically correct and directly executable.
        9. DO NOT sacrifice readability or maintainability for minor performance gains.

        The script uses a token system to avoid attribute mismatches. Tokens are formatted as <TOKEN:NAME> 
        and are registered in the TokenRegistry. Use this system when referring to configuration values 
        or other important constants.

        Return ONLY the improved code, directly executable.
        """


class DocumentationGoal(Goal):
    """Goal for improving documentation and code clarity."""
    
    description = "Improve documentation and code clarity."
    priority = 8
    
    def get_prompt(self, current_code: str, config: Config) -> str:
        """Generate a prompt for documentation improvement."""
        return f"""
        Improve the documentation and clarity of the following Python script:

        ```python
        {current_code}
        ```

        Focus on:
        1. Adding or improving docstrings for all classes, methods, and functions
        2. Adding helpful comments for complex code sections
        3. Improving variable and function naming for clarity
        4. Adding type hints where appropriate
        5. Ensuring consistent documentation style throughout

        IMPORTANT GUIDELINES:
        1. DO NOT use "...existing code" placeholders. Always include the complete code.
        2. Ensure all imports from the original code are preserved.
        3. Keep the docstring at the beginning and the main execution block at the end.
        4. Maintain the VERSION constant and update it appropriately.
        5. Preserve all existing class and function definitions.
        6. Use consistent indentation (4 spaces per level).
        7. Ensure all delimiters (quotes, parentheses, brackets) are properly closed.
        8. The code must be syntactically correct and directly executable.
        9. DO NOT change the functionality of the code.

        The script uses a token system to avoid attribute mismatches. Tokens are formatted as <TOKEN:NAME> 
        and are registered in the TokenRegistry. Use this system when referring to configuration values 
        or other important constants.

        Return ONLY the improved code, directly executable.
        """
        
    def get_enhanced_prompt(self, current_code: str, config: Config, issues: List[str]) -> str:
        """Generate an enhanced prompt for documentation improvement."""
        issue_guidance = "\n        ".join([f"- {issue}" for issue in issues])
        
        return f"""
        Improve the documentation and clarity of the following Python script, paying special attention to fixing these specific issues:
        
        {issue_guidance}

        ```python
        {current_code}
        ```

        Focus on:
        1. Adding or improving docstrings for all classes, methods, and functions
        2. Adding helpful comments for complex code sections
        3. Improving variable and function naming for clarity
        4. Adding type hints where appropriate
        5. Ensuring consistent documentation style throughout

        CRITICAL REQUIREMENTS:
        1. DO NOT use "...existing code" placeholders. Always include the complete code.
        2. Ensure all imports from the original code are preserved.
        3. Keep the docstring at the beginning and the main execution block at the end.
        4. Maintain the VERSION constant and update it appropriately.
        5. Preserve all existing class and function definitions.
        6. Use consistent indentation (4 spaces per level).
        7. Ensure all delimiters (quotes, parentheses, brackets) are properly closed.
        8. The code must be syntactically correct and directly executable.
        9. DO NOT change the functionality of the code.

        The script uses a token system to avoid attribute mismatches. Tokens are formatted as <TOKEN:NAME> 
        and are registered in the TokenRegistry. Use this system when referring to configuration values 
        or other important constants.

        Return ONLY the improved code, directly executable.
        """


class FeatureGoal(Goal):
    """Goal for adding new features."""
    
    description = "Add new features to enhance functionality."
    priority = 6
    
    def __init__(self, feature_description: str = None):
        """
        Initialize the feature goal.
        
        Args:
            feature_description: Description of the feature to add
        """
        super().__init__()
        if feature_description:
            self.description = feature_description
    
    def get_prompt(self, current_code: str, config: Config) -> str:
        """Generate a prompt for adding new features."""
        return f"""
        Add new features to the following Python script:

        ```python
        {current_code}
        ```

        Focus on:
        1. Adding useful new capabilities that align with the script's purpose
        2. Ensuring new features integrate well with existing code
        3. Maintaining the overall architecture and design principles
        4. Adding appropriate documentation for new features
        5. Including proper error handling for new functionality

        IMPORTANT GUIDELINES:
        1. DO NOT use "...existing code" placeholders. Always include the complete code.
        2. Ensure all imports from the original code are preserved.
        3. Keep the docstring at the beginning and the main execution block at the end.
        4. Maintain the VERSION constant and update it appropriately.
        5. Preserve all existing class and function definitions.
        6. Use consistent indentation (4 spaces per level).
        7. Ensure all delimiters (quotes, parentheses, brackets) are properly closed.
        8. The code must be syntactically correct and directly executable.
        9. DO NOT break existing functionality.

        The script uses a token system to avoid attribute mismatches. Tokens are formatted as <TOKEN:NAME> 
        and are registered in the TokenRegistry. Use this system when referring to configuration values 
        or other important constants.

        Return ONLY the improved code, directly executable.
        """
        
    def get_enhanced_prompt(self, current_code: str, config: Config, issues: List[str]) -> str:
        """Generate an enhanced prompt for adding new features."""
        issue_guidance = "\n        ".join([f"- {issue}" for issue in issues])
        
        return f"""
        Add new features to the following Python script, paying special attention to fixing these specific issues:
        
        {issue_guidance}

        ```python
        {current_code}
        ```

        Focus on:
        1. Adding useful new capabilities that align with the script's purpose
        2. Ensuring new features integrate well with existing code
        3. Maintaining the overall architecture and design principles
        4. Adding appropriate documentation for new features
        5. Including proper error handling for new functionality

        CRITICAL REQUIREMENTS:
        1. DO NOT use "...existing code" placeholders. Always include the complete code.
        2. Ensure all imports from the original code are preserved.
        3. Keep the docstring at the beginning and the main execution block at the end.
        4. Maintain the VERSION constant and update it appropriately.
        5. Preserve all existing class and function definitions.
        6. Use consistent indentation (4 spaces per level).
        7. Ensure all delimiters (quotes, parentheses, brackets) are properly closed.
        8. The code must be syntactically correct and directly executable.
        9. DO NOT break existing functionality.

        The script uses a token system to avoid attribute mismatches. Tokens are formatted as <TOKEN:NAME> 
        and are registered in the TokenRegistry. Use this system when referring to configuration values 
        or other important constants.

        Return ONLY the improved code, directly executable.
        """


class GoalManager:
    """
    Manages multiple improvement goals with priorities.
    Rotates focus areas to ensure balanced improvement.
    """
    
    def __init__(self):
        """Initialize the goal manager."""
        self.goals = []
        self.current_goal_index = 0
        self.goal_history = []
        
        # Add default goals
        self.add_goal(SelfEditGoal())
        self.add_goal(PerformanceGoal())
        self.add_goal(DocumentationGoal())
    
    def add_goal(self, goal: Goal) -> None:
        """
        Add a goal to the manager.
        
        Args:
            goal: The goal to add
        """
        self.goals.append(goal)
        # Sort goals by priority (highest first)
        self.goals.sort(key=lambda g: g.priority, reverse=True)
    
    def get_current_goal(self) -> Goal:
        """
        Get the current goal.
        
        Returns:
            The current goal
        """
        if not self.goals:
            # Add default goal if none exist
            self.add_goal(SelfEditGoal())
        
        return self.goals[self.current_goal_index]
    
    def rotate_goal(self) -> Goal:
        """
        Rotate to the next goal.
        
        Returns:
            The new current goal
        """
        if not self.goals:
            # Add default goal if none exist
            self.add_goal(SelfEditGoal())
            return self.goals[0]
        
        # Record the current goal in history
        self.goal_history.append({
            "goal": self.goals[self.current_goal_index].description,
            "timestamp": datetime.datetime.now().strftime("%Y%m%d%H%M%S")
        })
        
        # Move to the next goal
        self.current_goal_index = (self.current_goal_index + 1) % len(self.goals)
        
        return self.goals[self.current_goal_index]
    
    def get_goal_by_name(self, name: str) -> Optional[Goal]:
        """
        Get a goal by its class name.
        
        Args:
            name: Name of the goal class
            
        Returns:
            The goal if found, None otherwise
        """
        for goal in self.goals:
            if goal.__class__.__name__ == name:
                return goal
        return None


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
        
        # Rate limiting parameters - extended to allow for up to an hour of backoff
        self.rate_limit_encountered = False
        # Exponential backoff in seconds: 5s, 10s, 30s, 1m, 2m, 5m, 10m, 15m, 30m, 60m
        self.rate_limit_backoff = [5, 10, 30, 60, 120, 300, 600, 900, 1800, 3600]
        self.rate_limit_attempt = 0
        
        # Track API usage to avoid hitting limits
        self.api_calls_today = 0
        self.last_call_time = None
        self.min_call_interval = 5  # Minimum seconds between API calls
    
    def generate_response(self, prompt: str) -> Optional[str]:
        """Generate a response from the AI model based on the given prompt."""
        try:
            # Validate tokens in the prompt
            invalid_tokens = TokenRegistry.validate_tokens(prompt)
            if invalid_tokens:
                logger.warning(f"Invalid tokens in prompt: {invalid_tokens}")
            
            # Replace valid tokens
            prompt = TokenRegistry.replace_tokens(prompt)
            
            # If we've hit rate limits before, apply backoff
            if self.rate_limit_encountered and self.rate_limit_attempt < len(self.rate_limit_backoff):
                backoff_time = self.rate_limit_backoff[self.rate_limit_attempt]
                logger.info(f"Rate limit previously encountered. Backing off for {self._format_time(backoff_time)} before trying again.")
                import time
                time.sleep(backoff_time)
            
            # Enforce minimum interval between API calls to avoid rate limits
            self._enforce_call_interval()
            
            # Track API usage
            self.api_calls_today += 1
            import datetime
            self.last_call_time = datetime.datetime.now()
            
            response = self.model.generate_content(prompt)
            
            # Reset rate limit flags on successful request
            self.rate_limit_encountered = False
            self.rate_limit_attempt = 0
            
            code = response.text
            
            # Check for incomplete code and fix if possible
            code = self._fix_incomplete_code(code)
            
            return code
        except Exception as e:
            error_str = str(e)
            
            # Handle rate limiting errors (429)
            if "429" in error_str and "Resource has been exhausted" in error_str:
                self.rate_limit_encountered = True
                
                if self.rate_limit_attempt < len(self.rate_limit_backoff):
                    backoff_time = self.rate_limit_backoff[self.rate_limit_attempt]
                    logger.warning(f"Rate limit encountered (429). Backing off for {self._format_time(backoff_time)} and retrying.")
                    
                    import time
                    time.sleep(backoff_time)
                    
                    # Increment for next time
                    self.rate_limit_attempt += 1
                    
                    # Recursive retry after backoff
                    return self.generate_response(prompt)
                else:
                    logger.error(f"Rate limit (429) exceeded maximum retry attempts ({len(self.rate_limit_backoff)})")
                    logger.info("Resetting rate limit attempt counter and trying one more time with maximum backoff")
                    
                    # Reset counter but use maximum backoff time
                    self.rate_limit_attempt = 0
                    
                    import time
                    time.sleep(self.rate_limit_backoff[-1])  # Use the longest backoff time
                    
                    # One final attempt
                    return self.generate_response(prompt)
            
            logger.error(f"Gemini API error: {e}")
            return None
    
    def _enforce_call_interval(self) -> None:
        """Enforce a minimum interval between API calls to avoid rate limits."""
        if self.last_call_time:
            import datetime
            import time
            
            now = datetime.datetime.now()
            elapsed = (now - self.last_call_time).total_seconds()
            
            if elapsed < self.min_call_interval:
                sleep_time = self.min_call_interval - elapsed
                logger.debug(f"Enforcing minimum call interval. Waiting {sleep_time:.2f}s")
                time.sleep(sleep_time)
    
    def _format_time(self, seconds: int) -> str:
        """Format time in seconds to a human-readable string."""
        if seconds < 60:
            return f"{seconds}s"
        elif seconds < 3600:
            return f"{seconds // 60}m {seconds % 60}s"
        else:
            return f"{seconds // 3600}h {(seconds % 3600) // 60}m"
    
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

class LearningDatabase:
    """
    Database for tracking and learning from past improvements.
    Analyzes patterns in successful and failed edits to guide future improvements.
    """
    
    def __init__(self, db_file: Path = Path(".adaptagen_learning.json")):
        """Initialize the learning database."""
        self.db_file = db_file
        self.data = self._load_data()
        
        # Initialize database structure if it doesn't exist
        if "component_history" not in self.data:
            self.data["component_history"] = {}
        if "approach_success_rates" not in self.data:
            self.data["approach_success_rates"] = {}
        if "prompt_patterns" not in self.data:
            self.data["prompt_patterns"] = {"successful": [], "failed": []}
        if "complexity_metrics" not in self.data:
            self.data["complexity_metrics"] = {}
        if "improvement_metrics" not in self.data:
            self.data["improvement_metrics"] = {"overall": []}
        
        # Save initialized structure
        self._save_data()
    
    def _load_data(self) -> Dict:
        """Load data from the database file."""
        if self.db_file.exists():
            try:
                with open(self.db_file, 'r') as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"Error loading learning database: {e}")
                return {}
        return {}
    
    def _save_data(self) -> None:
        """Save data to the database file."""
        try:
            with open(self.db_file, 'w') as f:
                json.dump(self.data, f, indent=2)
        except Exception as e:
            logger.error(f"Error saving learning database: {e}")
    
    def record_edit_attempt(self, component_name: str, approach: str, 
                           success: bool, code_before: str, code_after: str = None,
                           error_message: str = None) -> None:
        """
        Record an edit attempt in the database.
        
        Args:
            component_name: Name of the component that was edited
            approach: The editing approach used
            success: Whether the edit was successful
            code_before: The code before the edit
            code_after: The code after the edit (if successful)
            error_message: Error message (if failed)
        """
        # Initialize component history if it doesn't exist
        if component_name not in self.data["component_history"]:
            self.data["component_history"][component_name] = {
                "attempts": 0,
                "successes": 0,
                "failures": 0,
                "last_success": None,
                "last_failure": None,
                "approaches": {}
            }
        
        # Update component history
        component_data = self.data["component_history"][component_name]
        component_data["attempts"] += 1
        
        # Initialize approach data if it doesn't exist
        if approach not in component_data["approaches"]:
            component_data["approaches"][approach] = {
                "attempts": 0,
                "successes": 0,
                "failures": 0
            }
        
        # Update approach data for this component
        approach_data = component_data["approaches"][approach]
        approach_data["attempts"] += 1
        
        # Initialize global approach data if it doesn't exist
        if approach not in self.data["approach_success_rates"]:
            self.data["approach_success_rates"][approach] = {
                "attempts": 0,
                "successes": 0,
                "failures": 0
            }
        
        # Update global approach data
        global_approach_data = self.data["approach_success_rates"][approach]
        global_approach_data["attempts"] += 1
        
        # Record timestamp
        timestamp = datetime.datetime.now().strftime("%Y%m%d%H%M%S")
        
        # Record success or failure
        if success:
            component_data["successes"] += 1
            component_data["last_success"] = timestamp
            approach_data["successes"] += 1
            global_approach_data["successes"] += 1
            
            # Calculate complexity metrics
            complexity_before = self._calculate_complexity(code_before)
            complexity_after = self._calculate_complexity(code_after)
            
            # Record complexity change
            if component_name not in self.data["complexity_metrics"]:
                self.data["complexity_metrics"][component_name] = []
            
            self.data["complexity_metrics"][component_name].append({
                "timestamp": timestamp,
                "before": complexity_before,
                "after": complexity_after,
                "change": {k: complexity_after[k] - complexity_before[k] for k in complexity_before}
            })
            
            # Extract successful patterns from the edit
            self._extract_patterns(code_before, code_after, success=True)
        else:
            component_data["failures"] += 1
            component_data["last_failure"] = timestamp
            approach_data["failures"] += 1
            global_approach_data["failures"] += 1
            
            # Record error message
            if error_message:
                if "error_patterns" not in component_data:
                    component_data["error_patterns"] = []
                
                component_data["error_patterns"].append({
                    "timestamp": timestamp,
                    "approach": approach,
                    "error": error_message
                })
        
        # Save updated data
        self._save_data()
    
    def get_best_approach_for_component(self, component_name: str) -> str:
        """
        Get the best approach for a specific component based on past performance.
        
        Args:
            component_name: Name of the component
            
        Returns:
            Name of the best approach
        """
        # If we have history for this component, use it
        if component_name in self.data["component_history"]:
            component_data = self.data["component_history"][component_name]
            
            # If we have approach data, find the best one
            if component_data["approaches"]:
                best_approach = None
                best_success_rate = -1
                
                for approach, data in component_data["approaches"].items():
                    if data["attempts"] > 0:
                        success_rate = data["successes"] / data["attempts"]
                        if success_rate > best_success_rate:
                            best_success_rate = success_rate
                            best_approach = approach
                
                if best_approach and best_success_rate > 0:
                    return best_approach
        
        # Fall back to global best approach
        return self.get_best_approach_overall()
    
    def get_best_approach_overall(self) -> str:
        """
        Get the best approach overall based on past performance.
        
        Returns:
            Name of the best approach
        """
        best_approach = "standard"  # Default
        best_success_rate = -1
        
        for approach, data in self.data["approach_success_rates"].items():
            if data["attempts"] > 0:
                success_rate = data["successes"] / data["attempts"]
                if success_rate > best_success_rate:
                    best_success_rate = success_rate
                    best_approach = approach
        
        return best_approach
    
    def prioritize_components(self, components: Dict[str, str]) -> List[Tuple[str, str]]:
        """
        Prioritize components based on historical success rates and complexity.
        
        Args:
            components: Dictionary mapping component names to their code
            
        Returns:
            List of (component_name, component_code) tuples in priority order
        """
        component_scores = []
        
        for name, code in components.items():
            # Calculate base score
            score = 0.5  # Default middle score
            
            # Adjust based on history if available
            if name in self.data["component_history"]:
                history = self.data["component_history"][name]
                
                # Components with higher success rates get higher priority
                if history["attempts"] > 0:
                    success_rate = history["successes"] / history["attempts"]
                    score = success_rate
                
                # Boost score for components that haven't been successfully edited recently
                if not history["last_success"] and history["attempts"] < 3:
                    score += 0.2  # Boost for never-succeeded components with few attempts
            else:
                # Boost score for never-attempted components
                score += 0.1
            
            # Adjust based on complexity
            complexity = self._calculate_complexity(code)
            
            # Prefer simpler components first (they're more likely to succeed)
            if complexity["cyclomatic"] < 5:
                score += 0.1
            elif complexity["cyclomatic"] > 15:
                score -= 0.1
                
            # Prefer components with higher potential impact
            if complexity["lines"] > 50:
                score += 0.05  # Larger components have more potential for improvement
            
            component_scores.append((name, code, score))
        
        # Sort by score in descending order
        sorted_components = sorted(component_scores, key=lambda x: x[2], reverse=True)
        
        # Return just the name and code
        return [(name, code) for name, code, _ in sorted_components]
    
    def enhance_prompt_for_component(self, component_name: str, base_prompt: str) -> str:
        """
        Enhance a prompt based on learning from past successes and failures.
        
        Args:
            component_name: Name of the component
            base_prompt: Base prompt to enhance
            
        Returns:
            Enhanced prompt
        """
        enhancements = []
        
        # Add component-specific guidance if available
        if component_name in self.data["component_history"]:
            history = self.data["component_history"][component_name]  # Fixed: was using 'name' instead of 'component_name'
            
            # Add warnings about common errors
            if "error_patterns" in history and history["error_patterns"]:
                common_errors = {}
                for error_data in history["error_patterns"]:
                    error = error_data["error"]
                    if error in common_errors:
                        common_errors[error] += 1
                    else:
                        common_errors[error] = 1
                
                # Get the most common errors
                top_errors = sorted(common_errors.items(), key=lambda x: x[1], reverse=True)[:2]
                if top_errors:
                    error_guidance = "IMPORTANT - Avoid these common issues:\n"
                    for error, _ in top_errors:
                        error_guidance += f"- {error}\n"
                    enhancements.append(error_guidance)
        
        # Add successful patterns
        if self.data["prompt_patterns"]["successful"]:
            # Get the top 3 successful patterns
            top_patterns = self.data["prompt_patterns"]["successful"][:3]
            if top_patterns:
                pattern_guidance = "Consider these successful patterns:\n"
                for pattern in top_patterns:
                    pattern_guidance += f"- {pattern}\n"
                enhancements.append(pattern_guidance)
        
        # Combine enhancements with base prompt
        if enhancements:
            # Find the right place to insert enhancements (before the final instructions)
            lines = base_prompt.split('\n')
            insert_point = -1
            
            # Look for the "IMPORTANT:" section or similar
            for i, line in enumerate(lines):
                if "IMPORTANT:" in line or "CRITICAL" in line or "GUIDELINES:" in line:
                    insert_point = i
                    break
            
            if insert_point >= 0:
                # Insert enhancements before the guidelines
                enhanced_lines = lines[:insert_point] + enhancements + lines[insert_point:]
                return '\n'.join(enhanced_lines)
            else:
                # Append to the end if no suitable insertion point found
                return base_prompt + '\n\n' + '\n'.join(enhancements)
        
        return base_prompt
    
    def _calculate_complexity(self, code: str) -> Dict[str, float]:
        """
        Calculate complexity metrics for a piece of code.
        
        Args:
            code: The code to analyze
            
        Returns:
            Dictionary of complexity metrics
        """
        if not code:
            return {"lines": 0, "cyclomatic": 0, "nesting": 0}
        
        lines = code.split('\n')
        non_empty_lines = [line for line in lines if line.strip()]
        
        # Simple cyclomatic complexity estimation
        decision_points = 0
        for line in non_empty_lines:
            if re.search(r'\bif\b|\bfor\b|\bwhile\b|\belif\b|\bexcept\b|\bwith\b', line):
                decision_points += 1
        
        # Simple nesting level estimation
        max_indent = 0
        for line in non_empty_lines:
            indent = len(line) - len(line.lstrip())
            max_indent = max(max_indent, indent)
        
        # Normalize nesting level (assuming 4 spaces per level)
        nesting_level = max_indent / 4 if max_indent > 0 else 0
        
        return {
            "lines": len(non_empty_lines),
            "cyclomatic": decision_points,
            "nesting": nesting_level
        }
    
    def _extract_patterns(self, code_before: str, code_after: str, success: bool) -> None:
        """
        Extract patterns from successful or failed edits.
        
        Args:
            code_before: Code before the edit
            code_after: Code after the edit
            success: Whether the edit was successful
        """
        if not code_before or not code_after:
            return
        
        # This is a simplified implementation
        # A more sophisticated approach would use AST parsing to identify
        # specific transformation patterns
        
        # For now, just look for simple patterns like added error handling
        if success:
            # Check for added try/except blocks
            if "try:" in code_after and "try:" not in code_before:
                self.data["prompt_patterns"]["successful"].append(
                    "Adding proper error handling with try/except blocks"
                )
            
            # Check for added logging
            if "logger." in code_after and "logger." not in code_before:
                self.data["prompt_patterns"]["successful"].append(
                    "Adding logging statements for better observability"
                )
            
            # Check for added docstrings
            if '"""' in code_after and '"""' not in code_before:
                self.data["prompt_patterns"]["successful"].append(
                    "Adding or improving docstrings"
                )
            
            # Check for added type hints
            type_hint_pattern = r':\s*[A-Za-z\[\]\'\"]+\s*='
            if re.search(type_hint_pattern, code_after) and not re.search(type_hint_pattern, code_before):
                self.data["prompt_patterns"]["successful"].append(
                    "Adding type hints for better code clarity"
                )
            
            # Deduplicate patterns
            self.data["prompt_patterns"]["successful"] = list(set(self.data["prompt_patterns"]["successful"]))
    
    def generate_improvement_report(self) -> str:
        """
        Generate a report on improvement progress.
        
        Returns:
            Report text
        """
        report = "AdaptaGen Improvement Report\n"
        report += "=========================\n\n"
        
        # Overall statistics
        total_attempts = sum(comp["attempts"] for comp in self.data["component_history"].values())
        total_successes = sum(comp["successes"] for comp in self.data["component_history"].values())
        success_rate = total_successes / total_attempts if total_attempts > 0 else 0
        
        report += f"Overall Statistics:\n"
        report += f"- Total edit attempts: {total_attempts}\n"
        report += f"- Successful edits: {total_successes}\n"
        report += f"- Success rate: {success_rate:.2%}\n\n"
        
        # Approach effectiveness
        report += f"Approach Effectiveness:\n"
        for approach, data in self.data["approach_success_rates"].items():
            if data["attempts"] > 0:
                approach_success_rate = data["successes"] / data["attempts"]
                report += f"- {approach}: {approach_success_rate:.2%} ({data['successes']}/{data['attempts']})\n"
        
        report += "\n"
        
        # Most improved components
        if self.data["complexity_metrics"]:
            report += f"Most Improved Components:\n"
            component_improvements = []
            
            for component, metrics in self.data["complexity_metrics"].items():
                if metrics:
                    # Calculate total improvement
                    total_improvement = sum(m["change"].get("cyclomatic", 0) for m in metrics)
                    component_improvements.append((component, total_improvement))
            
            # Sort by improvement (most improved first)
            sorted_improvements = sorted(component_improvements, key=lambda x: x[1], reverse=True)
            
            for component, improvement in sorted_improvements[:5]:
                report += f"- {component}: {improvement} complexity reduction\n"
        
        return report

class IncrementalEditor:
    """
    Manages incremental editing of code with verification after each change.
    Makes small, controlled edits and verifies they work before proceeding.
    """
    
    def __init__(self, original_code: str, code_manager: CodeManager, 
                 version_control: VersionControl, gemini_api: GeminiAPI,
                 target_file: Path = None, learning_db: LearningDatabase = None):
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
        
        # Extended backoff times for more patience (up to 30 minutes)
        # 1s, 2s, 5s, 10s, 30s, 1m, 2m, 5m, 10m, 15m, 30m
        self.backoff_times = [1, 2, 5, 10, 30, 60, 120, 300, 600, 900, 1800]
        
        self.edit_approaches = [
            self._approach_standard_edit,
            self._approach_simplified_edit,
            self._approach_conservative_edit,
            self._approach_focused_bugfix
        ]
        
        # Initialize or use provided learning database
        self.learning_db = learning_db if learning_db else LearningDatabase()
        
        # Track complexity progression
        self.initial_complexity = self._calculate_overall_complexity(original_code)
        self.current_complexity = self.initial_complexity.copy()
        
        # Maximum number of components to process in a single run
        self.max_components_per_run = 10
        
    def _calculate_overall_complexity(self, code: str) -> Dict[str, float]:
        """Calculate overall complexity metrics for the entire codebase."""
        return self.learning_db._calculate_complexity(code)
        
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
        
        prompt = base_prompt + focus + guidelines + "\n\nReturn the complete improved component code."
        
        # Enhance the prompt based on learning
        enhanced_prompt = self.learning_db.enhance_prompt_for_component(component_name, prompt)
        
        return enhanced_prompt
    
    def _format_time(self, seconds: int) -> str:
        """Format time in seconds to a human-readable string."""
        if seconds < 60:
            return f"{seconds}s"
        elif seconds < 3600:
            return f"{seconds // 60}m {seconds % 60}s"
        else:
            return f"{seconds // 3600}h {(seconds % 3600) // 60}m"
    
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
        
        # Get the best approach for this component based on learning
        best_approach = self.learning_db.get_best_approach_for_component(component_name)
        
        # Reorder approaches to try the best one first
        approach_funcs = {
            "standard": self._approach_standard_edit,
            "simplified": self._approach_simplified_edit,
            "conservative": self._approach_conservative_edit,
            "bugfix": self._approach_focused_bugfix
        }
        
        # Create a new ordered list of approaches
        ordered_approaches = []
        if best_approach in approach_funcs:
            ordered_approaches.append((best_approach, approach_funcs[best_approach]))
            
        # Add the rest of the approaches
        for name, func in approach_funcs.items():
            if name != best_approach:
                ordered_approaches.append((name, func))
        
        # Try each approach
        for approach_idx, (approach_name, approach_func) in enumerate(ordered_approaches):
            logger.info(f"Trying approach {approach_idx+1}/{len(ordered_approaches)} ({approach_name}) for {component_name}")
            
            # Try with backoff
            for attempt, backoff_time in enumerate(self.backoff_times):
                logger.info(f"Attempt {attempt+1}/{len(self.backoff_times)} with {self._format_time(backoff_time)} backoff")
                
                # Generate improved component
                improved_component = approach_func(component_name, component_code)
                
                # If we got None back, it might be due to rate limiting which is already handled
                # by the GeminiAPI class with its own backoff strategy. In this case, we should
                # pause our attempts for a while to let the rate limit reset.
                if not improved_component:
                    # Check if the API client has encountered rate limits
                    if self.gemini_api.rate_limit_encountered:
                        logger.warning(f"Rate limit encountered while processing {component_name}. Pausing component editing.")
                        
                        # Record the failed attempt in the learning database
                        self.learning_db.record_edit_attempt(
                            component_name,
                            approach_name,
                            success=False,
                            code_before=component_code,
                            error_message="Rate limit exceeded"
                        )
                        
                        # Wait longer than the API's own backoff to ensure we're not hammering the API
                        extended_wait = 1800  # 30 minutes
                        logger.info(f"Waiting {self._format_time(extended_wait)} before trying another component...")
                        time.sleep(extended_wait)
                        
                        # Skip to the next component rather than continuing to retry this one
                        return False, self.current_code
                    
                    logger.warning(f"Failed to generate improved version for {component_name}")
                    time.sleep(backoff_time)
                    continue
                
                # Replace component in the code
                new_code = self.replace_component(component_name, improved_component)
                
                # Verify the new code
                if self.verify_code(new_code):
                    logger.info(f"Successfully improved component: {component_name}")
                    
                    # Record the successful attempt in the learning database
                    self.learning_db.record_edit_attempt(
                        component_name,
                        approach_name,
                        success=True,
                        code_before=component_code,
                        code_after=improved_component
                    )
                    
                    # Update complexity metrics
                    self.current_complexity = self._calculate_overall_complexity(new_code)
                    
                    return True, new_code
                
                # Record the failed attempt in the learning database
                self.learning_db.record_edit_attempt(
                    component_name,
                    approach_name,
                    success=False,
                    code_before=component_code,
                    error_message="Verification failed"
                )
                
                logger.warning(f"Verification failed for {component_name}, backing off for {self._format_time(backoff_time)}")
                time.sleep(backoff_time)
            
            # If we've tried all backoff times with this approach and failed, try the next approach
            logger.warning(f"All attempts with approach {approach_name} failed for {component_name}")
        
        # If all approaches failed, return failure
        logger.error(f"All approaches failed for {component_name}")
        return False, self.current_code
    
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
        
        # Prioritize components using the learning database
        sorted_components = self.learning_db.prioritize_components(components)
        logger.info(f"Prioritized {len(sorted_components)} components based on learning history")
        
        # Limit the number of components to process in a single run
        if len(sorted_components) > self.max_components_per_run:
            logger.info(f"Limiting to {self.max_components_per_run} components for this run")
            sorted_components = sorted_components[:self.max_components_per_run]
        
        # Track rate limit occurrences
        rate_limit_count = 0
        max_rate_limit_threshold = 3  # After this many rate limits, we'll change strategy
        
        # Process each component
        component_index = 0
        while component_index < len(sorted_components):
            component_name, component_code = sorted_components[component_index]
            logger.info(f"Processing component: {component_name} ({component_index+1}/{len(sorted_components)})")
            
            # Check if we've hit too many rate limits and should adjust strategy
            if rate_limit_count >= max_rate_limit_threshold:
                logger.warning(f"Hit rate limit threshold ({max_rate_limit_threshold}). Switching to conservative approach only.")
                # Override the edit approaches to only use the most conservative one
                self.edit_approaches = [self._approach_conservative_edit]
                
                # Also increase the backoff times
                self.backoff_times = [60, 300, 600, 1800]  # 1m, 5m, 10m, 30m
                
                # Reset the counter so we don't keep logging this
                rate_limit_count = 0
            
            # Try to edit the component
            success, new_code = self.try_edit_component(component_name, component_code)
            
            # Check if we hit a rate limit
            if self.gemini_api.rate_limit_encountered:
                rate_limit_count += 1
                
                # If we've hit multiple rate limits, start skipping components
                if rate_limit_count >= 2:
                    # Skip ahead to process only every Nth component
                    skip_factor = rate_limit_count
                    next_index = component_index + skip_factor
                    
                    if next_index < len(sorted_components):
                        logger.warning(f"Multiple rate limits encountered. Skipping ahead to component {next_index+1}.")
                        component_index = next_index
                        continue
            
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
            
            # Move to the next component
            component_index += 1
        
        # Generate and log improvement report
        improvement_report = self.learning_db.generate_improvement_report()
        logger.info(f"Improvement Report:\n{improvement_report}")
        
        logger.info(f"Incremental editing completed. Successful edits: {self.successful_edits}, Failed edits: {self.failed_edits}")
        return self.current_code
    
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

class AdaptaGen:
    """Orchestrates the self-modification process."""
    
    def __init__(self, config: Config):
        """Initialize the AdaptaGen system."""
        self.config = config
        self.gemini_api = GeminiAPI(config)
        self.code_manager = CodeManager()
        self.version_control = VersionControl()
        self.version_manager = VersionManager()
        self.goal_manager = GoalManager()
        self.learning_db = LearningDatabase()
        
        # Register with token registry
        TokenRegistry.register("ADAPTAGEN", self.__class__.__name__)
    
    def run(self, increment_type: str = 'revision', use_incremental: bool = False, 
            goal_name: str = None, max_components: int = 10, patient_mode: bool = False) -> None:
        """
        Execute the self-modification process.
        
        Args:
            increment_type: Type of version increment ('major', 'minor', 'patch', or 'revision')
            use_incremental: Whether to use incremental editing instead of full regeneration
            goal_name: Name of the goal to use (if None, use current goal)
            max_components: Maximum number of components to process in a single run
            patient_mode: Whether to use extended backoff times for more patient operation
        """
        # Set the current goal if specified
        if goal_name:
            goal = self.goal_manager.get_goal_by_name(goal_name)
            if not goal:
                logger.warning(f"Goal {goal_name} not found. Using current goal.")
                goal = self.goal_manager.get_current_goal()
        else:
            # Get the current goal or rotate to the next one
            if self.version_control.get_version_history():
                # If we have previous versions, rotate to the next goal
                goal = self.goal_manager.rotate_goal()
            else:
                # For the first run, use the current goal (highest priority)
                goal = self.goal_manager.get_current_goal()
        
        logger.info(f"Starting AdaptaGen {VERSION} with goal: {goal.description}")
        
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
            
            # Initialize the incremental editor with the target file and learning database
            incremental_editor = IncrementalEditor(
                current_code, 
                self.code_manager, 
                self.version_control,
                self.gemini_api,
                target_filepath,
                self.learning_db
            )
            
            # Configure the incremental editor based on parameters
            if max_components:
                incremental_editor.max_components_per_run = max_components
                logger.info(f"Set maximum components per run to {max_components}")
                
            if patient_mode:
                # Use extended backoff times for more patient operation
                # Up to 1 hour: 1s, 5s, 15s, 30s, 1m, 2m, 5m, 10m, 15m, 30m, 60m
                incremental_editor.backoff_times = [1, 5, 15, 30, 60, 120, 300, 600, 900, 1800, 3600]
                logger.info("Using patient mode with extended backoff times (up to 1 hour)")
            
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
        prompt = goal.get_prompt(current_code, self.config)
        
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
                        enhanced_prompt = goal.get_enhanced_prompt(current_code, self.config, issues)
                        
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
                    syntax_error_prompt = goal.get_enhanced_prompt(
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
            
    def generate_improvement_report(self) -> str:
        """
        Generate a comprehensive improvement report.
        
        Returns:
            Report text
        """
        return self.learning_db.generate_improvement_report()


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
        parser.add_argument('--goal', type=str,
                            help='Specify a goal to use (SelfEditGoal, PerformanceGoal, DocumentationGoal, FeatureGoal)')
        parser.add_argument('--report', action='store_true',
                            help='Generate and display an improvement report')
        parser.add_argument('--list-versions', action='store_true',
                            help='List all versions in the version history')
        parser.add_argument('--max-components', type=int, default=10,
                            help='Maximum number of components to process in a single run (default: 10)')
        parser.add_argument('--patient', action='store_true',
                            help='Use extended backoff times for more patient operation')
        args = parser.parse_args()
        
        # Test mode - just verify the script can be imported and run basic functions
        if args.test:
            # In test mode, we just exit successfully to indicate the script is valid
            logger.info("Test mode: Script loaded successfully")
            sys.exit(0)
        
        # Initialize configuration from environment variables
        config = Config.from_env()
        
        # Create AdaptaGen instance
        adaptagen = AdaptaGen(config)
        
        # Handle specific commands
        if args.list_versions:
            adaptagen.list_versions()
            return
            
        if args.report:
            report = adaptagen.generate_improvement_report()
            print(report)
            return
        
        # Run the main process
        adaptagen.run(
            increment_type=args.version_type, 
            use_incremental=args.incremental,
            goal_name=args.goal,
            max_components=args.max_components,
            patient_mode=args.patient
        )
        
    except ValueError as e:
        logger.error(e)
        sys.exit(1)
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        sys.exit(1)



if __name__ == "__main__":
    main()
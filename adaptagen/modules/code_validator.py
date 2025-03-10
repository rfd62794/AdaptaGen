"""
Code Validation Module - Validates and fixes generated code for common issues.
"""

import re
import logging
from typing import List, Tuple

# Configure logging
logger = logging.getLogger(__name__)

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
        class_pattern = r'^class\s+(\w+)'
        
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
        function_pattern = r'^def\s+(\w+)'
        
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
                indent_size = len(line) - len(line.lstrip())
                if indent_size > 0:
                    indent_sizes.add(indent_size)
                    
        # If we have multiple indentation sizes that aren't multiples of each other
        if len(indent_sizes) > 1:
            min_indent = min(indent_sizes)
            for size in indent_sizes:
                if size % min_indent != 0:
                    return True
                    
        return False
        
    @staticmethod
    def _has_unclosed_delimiters(code: str) -> bool:
        """Check for unclosed delimiters."""
        # Check for unclosed parentheses, brackets, and braces
        delimiters = {'(': ')', '[': ']', '{': '}'}
        stack = []
        
        for char in code:
            if char in delimiters:
                stack.append(char)
            elif char in delimiters.values():
                if not stack or delimiters[stack.pop()] != char:
                    return True
                    
        # If stack is not empty, we have unclosed delimiters
        if stack:
            return True
            
        # Check for unclosed quotes
        quote_chars = ['"', "'"]
        for quote in quote_chars:
            if code.count(quote) % 2 != 0:
                return True
                
        return False
        
    @staticmethod
    def fix_common_issues(code: str, original_code: str) -> str:
        """
        Fix common issues in generated code.
        
        Args:
            code: The generated code to fix
            original_code: The original code for reference
            
        Returns:
            Fixed code
        """
        # Fix missing docstring
        if not code.strip().startswith('"""') and original_code.strip().startswith('"""'):
            # Extract docstring from original code
            docstring_end = original_code.find('"""', 3)
            if docstring_end > 0:
                docstring = original_code[:docstring_end + 3]
                code = docstring + "\n\n" + code
                
        # Fix missing imports
        original_imports = CodeValidator._extract_imports(original_code)
        new_imports = CodeValidator._extract_imports(code)
        
        missing_imports = [imp for imp in original_imports if imp not in new_imports]
        if missing_imports:
            # Find where imports end in the original code
            import_section = "\n".join(missing_imports)
            
            # Add missing imports after existing imports or at the beginning
            import_match = re.search(r'^import\s+[\w,\s.]+$', code, re.MULTILINE)
            if import_match:
                last_import_pos = code.rfind(import_match.group(0)) + len(import_match.group(0))
                code = code[:last_import_pos] + "\n" + import_section + code[last_import_pos:]
            else:
                # If no imports found, add after docstring or at the beginning
                if code.strip().startswith('"""'):
                    docstring_end = code.find('"""', 3)
                    if docstring_end > 0:
                        code = code[:docstring_end + 3] + "\n\n" + import_section + "\n" + code[docstring_end + 3:]
                else:
                    code = import_section + "\n\n" + code
                    
        # Fix missing main execution block
        if "if __name__ == \"__main__\":" not in code and "if __name__ == \"__main__\":" in original_code:
            # Extract main block from original code
            main_match = re.search(r'if\s+__name__\s*==\s*["\']__main__["\']\s*:(.*?)$', original_code, re.DOTALL)
            if main_match:
                main_block = main_match.group(0)
                code = code + "\n\n" + main_block
                
        # Fix missing VERSION constant
        if "VERSION = " not in code and "VERSION = " in original_code:
            version_match = re.search(r'VERSION\s*=\s*["\']([^"\']+)["\']', original_code)
            if version_match:
                version_line = f'VERSION = "{version_match.group(1)}"'
                
                # Add after imports or at the beginning
                import_match = re.search(r'^import\s+[\w,\s.]+$', code, re.MULTILINE)
                if import_match:
                    last_import_pos = code.rfind(import_match.group(0)) + len(import_match.group(0))
                    code = code[:last_import_pos] + "\n\n" + version_line + "\n" + code[last_import_pos:]
                else:
                    # If no imports found, add after docstring or at the beginning
                    if code.strip().startswith('"""'):
                        docstring_end = code.find('"""', 3)
                        if docstring_end > 0:
                            code = code[:docstring_end + 3] + "\n\n" + version_line + "\n" + code[docstring_end + 3:]
                    else:
                        code = version_line + "\n\n" + code
                        
        # Fix "...existing code" placeholders
        if "...existing code" in code:
            code = CodeValidator._fix_truncated_code(code, original_code)
            
        return code
        
    @staticmethod
    def _fix_truncated_code(code: str, original_code: str) -> str:
        """
        Fix truncated code by replacing "...existing code" placeholders.
        
        Args:
            code: The generated code with placeholders
            original_code: The original code to extract sections from
            
        Returns:
            Fixed code with placeholders replaced
        """
        # Split the code into lines
        lines = code.split('\n')
        result_lines = []
        
        i = 0
        while i < len(lines):
            line = lines[i]
            
            if "...existing code" in line:
                # Get context before and after the placeholder
                context_before = []
                context_after = []
                
                # Get up to 5 lines of context before
                for j in range(max(0, i - 5), i):
                    context_before.append(lines[j])
                    
                # Get up to 5 lines of context after
                for j in range(i + 1, min(len(lines), i + 6)):
                    context_after.append(lines[j])
                    
                # Find the corresponding section in the original code
                replacement = CodeValidator._find_section_in_original(context_before, context_after, original_code)
                
                if replacement:
                    # Add the replacement lines
                    result_lines.extend(replacement.split('\n'))
                else:
                    # If no replacement found, keep the placeholder
                    result_lines.append(line)
            else:
                result_lines.append(line)
                
            i += 1
            
        return '\n'.join(result_lines)
        
    @staticmethod
    def _find_section_in_original(context_before: List[str], context_after: List[str], original_code: str) -> str:
        """
        Find a section in the original code based on context.
        
        Args:
            context_before: Lines before the placeholder
            context_after: Lines after the placeholder
            original_code: The original code to search in
            
        Returns:
            The found section or empty string if not found
        """
        # Split the original code into lines
        original_lines = original_code.split('\n')
        
        # Clean up context lines (remove leading/trailing whitespace)
        context_before = [line.strip() for line in context_before if line.strip()]
        context_after = [line.strip() for line in context_after if line.strip()]
        
        if not context_before and not context_after:
            return ""
            
        # Try to find the section in the original code
        for i in range(len(original_lines)):
            # Check if the line matches the first line of context_before
            if context_before and original_lines[i].strip() == context_before[0]:
                # Check if subsequent lines match
                match_before = True
                for j in range(1, len(context_before)):
                    if i + j >= len(original_lines) or original_lines[i + j].strip() != context_before[j]:
                        match_before = False
                        break
                        
                if match_before:
                    # Find where context_after starts
                    start_idx = i + len(context_before)
                    end_idx = None
                    
                    if context_after:
                        for j in range(start_idx, len(original_lines)):
                            if original_lines[j].strip() == context_after[0]:
                                # Check if subsequent lines match
                                match_after = True
                                for k in range(1, len(context_after)):
                                    if j + k >= len(original_lines) or original_lines[j + k].strip() != context_after[k]:
                                        match_after = False
                                        break
                                        
                                if match_after:
                                    end_idx = j
                                    break
                    
                    if end_idx is None:
                        # If no end found, use a reasonable number of lines
                        end_idx = min(start_idx + 20, len(original_lines))
                        
                    # Extract the section
                    return '\n'.join(original_lines[start_idx:end_idx])
                    
        # If no exact match found, try a more flexible approach
        return CodeValidator._find_closest_section(context_before, context_after, original_lines)
        
    @staticmethod
    def _find_closest_section(context_before: List[str], context_after: List[str], original_lines: List[str]) -> str:
        """
        Find the closest matching section in the original code.
        
        Args:
            context_before: Lines before the placeholder
            context_after: Lines after the placeholder
            original_lines: Lines of the original code
            
        Returns:
            The closest matching section or empty string if not found
        """
        # If we have at least one line of context
        if context_before or context_after:
            # Try to find a line that matches any context line
            for i in range(len(original_lines)):
                for context_line in context_before + context_after:
                    if original_lines[i].strip() == context_line:
                        # Found a match, extract a reasonable section
                        start_idx = max(0, i - 10)
                        end_idx = min(i + 10, len(original_lines))
                        return '\n'.join(original_lines[start_idx:end_idx])
                        
        # If no match found, return empty string
        return "" 
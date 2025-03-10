"""
Code Manager Module - Handles reading, writing, and manipulating code.
"""

import re
import logging
from pathlib import Path
from typing import Dict, Optional, List

# Configure logging
logger = logging.getLogger(__name__)

class CodeManager:
    """Manages code reading, writing, and manipulation."""
    
    def __init__(self):
        """Initialize the code manager."""
        pass
        
    @staticmethod
    def read_code(filepath: Path) -> Optional[str]:
        """
        Read code from a file.
        
        Args:
            filepath: Path to the file
            
        Returns:
            The code as a string, or None if reading failed
        """
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                return f.read()
        except Exception as e:
            logger.error(f"Failed to read code from {filepath}: {e}")
            return None
            
    @staticmethod
    def write_code(filepath: Path, code: str) -> bool:
        """
        Write code to a file.
        
        Args:
            filepath: Path to the file
            code: The code to write
            
        Returns:
            True if writing succeeded, False otherwise
        """
        try:
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(code)
            return True
        except Exception as e:
            logger.error(f"Failed to write code to {filepath}: {e}")
            return False
            
    @staticmethod
    def calculate_hash(code: str) -> str:
        """Calculate a hash of the code."""
        import hashlib
        return hashlib.md5(code.encode('utf-8')).hexdigest()
        
    @staticmethod
    def extract_version(code: str) -> str:
        """Extract version string from code."""
        version_pattern = re.compile(r'VERSION\s*=\s*["\']([^"\']+)["\']')
        match = version_pattern.search(code)
        return match.group(1) if match else "unknown"
        
    @staticmethod
    def extract_components(code: str) -> Dict[str, str]:
        """
        Extract individual components (classes, functions) from the code.
        
        Args:
            code: The source code to extract components from
            
        Returns:
            Dictionary mapping component names to their code
        """
        components = {}
        
        try:
            # Extract classes
            class_pattern = re.compile(r'(class\s+(\w+)[\(:].*?)(?=class\s+\w+[\(:]|\Z)', re.DOTALL)
            for match in class_pattern.finditer(code):
                class_code = match.group(1)
                class_name = f"class {match.group(2)}"
                components[class_name] = class_code
                
            # Extract standalone functions
            function_pattern = re.compile(r'(def\s+(\w+)\s*\(.*?\).*?)(?=def\s+\w+\s*\(|\Z|class\s+\w+[\(:])', re.DOTALL)
            for match in function_pattern.finditer(code):
                # Skip methods inside classes
                if not re.search(r'^\s+def', match.group(1), re.MULTILINE):
                    function_code = match.group(1)
                    function_name = f"def {match.group(2)}"
                    components[function_name] = function_code
        except Exception as e:
            logger.error(f"Error extracting components: {str(e)}")
            # Return an empty dictionary if there was an error
            return {}
                
        return components
        
    @staticmethod
    def replace_component(code: str, component_name: str, new_component_code: str) -> str:
        """
        Replace a component in the code with its improved version.
        
        Args:
            code: The full source code
            component_name: Name of the component to replace (e.g., "class ClassName" or "def function_name")
            new_component_code: New code for the component
            
        Returns:
            Updated full code
        """
        try:
            if component_name.startswith("class "):
                class_name = component_name.split(" ")[1]
                # For classes
                class_pattern = re.compile(f'(class\\s+{class_name}[\\(:].*?)(?=class\\s+\\w+[\\(:]|\\Z)', re.DOTALL)
                if class_pattern.search(code):
                    return class_pattern.sub(new_component_code, code)
            elif component_name.startswith("def "):
                function_name = component_name.split(" ")[1]
                # For standalone functions
                function_pattern = re.compile(f'(def\\s+{function_name}\\s*\\(.*?\\).*?)(?=def\\s+\\w+\\s*\\(|\\Z|class\\s+\\w+[\\(:])', re.DOTALL)
                if function_pattern.search(code):
                    return function_pattern.sub(new_component_code, code)
                    
            # If component not found, return original code
            logger.warning(f"Component {component_name} not found in code")
            return code
        except Exception as e:
            logger.error(f"Error replacing component {component_name}: {str(e)}")
            # Return the original code if there was an error
            return code 
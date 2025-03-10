#!/usr/bin/env python3
"""
AdaptaGen Agent Template - Base template for the self-modifying AI agent.
This serves as a starting point for new versions.
"""

import os
import logging
import re
import time
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field, asdict

# Import required libraries
try:
    import google.generativeai as genai
    from dotenv import load_dotenv
except ImportError as e:
    raise ImportError(f"Required library not found: {e}. Please install with 'pip install -r requirements.txt'")

# Configure logging
logger = logging.getLogger(__name__)

# Constants
VERSION = "0.0.1"  # Will be updated by the agent
ENV_API_KEY = "GEMINI_API_KEY"
DEFAULT_MODEL_NAME = "gemini-pro"
DEFAULT_TEMPERATURE = 0.7
DEFAULT_MAX_OUTPUT_TOKENS = 8192
DEFAULT_TOP_P = 0.95
DEFAULT_TOP_K = 40

# Token control constants
TOKEN_PATTERN = r"<TOKEN:(\w+)>"
TOKEN_PREFIX = "<TOKEN:"
TOKEN_SUFFIX = ">"

@dataclass
class Token:
    """Token class for storing name-value pairs."""
    name: str
    value: Any

class TokenRegistry:
    """Registry for managing tokens used throughout the codebase."""
    
    _registry: Dict[str, Token] = {}
    
    @classmethod
    def register(cls, name: str, value: Any) -> None:
        """Register a token with a name and value."""
        cls._registry[name] = Token(name=name, value=value)
    
    @classmethod
    def get(cls, name: str, default: Any = None) -> Any:
        """Get a token value by name."""
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
        for match in re.finditer(TOKEN_PATTERN, text):
            token_name = match.group(1)
            # Skip 'NAME' tokens as they are expected to be handled differently
            if token_name == 'NAME':
                continue
            if token_name not in cls._registry:
                invalid_tokens.append(token_name)
        return invalid_tokens
    
    @classmethod
    def replace_tokens(cls, text: str) -> str:
        """Replace tokens in a text with their values."""
        for token in cls._registry.values():
            text = text.replace(cls.format_token(token.name), str(token.value))
        return text

@dataclass
class Config:
    """Configuration class for the agent."""
    
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
            model_name=os.getenv("GEMINI_MODEL", DEFAULT_MODEL_NAME),
            temperature=float(os.getenv("TEMPERATURE", DEFAULT_TEMPERATURE)),
            max_output_tokens=int(os.getenv("MAX_OUTPUT_TOKENS", DEFAULT_MAX_OUTPUT_TOKENS)),
            top_p=float(os.getenv("TOP_P", DEFAULT_TOP_P)),
            top_k=int(os.getenv("TOP_K", DEFAULT_TOP_K))
        )
        
        # Configure Gemini API
        genai.configure(api_key=config.api_key)
        
        return config
    
    def get_generation_config(self) -> Dict[str, Any]:
        """Get generation configuration for Gemini API."""
        return {
            "temperature": self.temperature,
            "max_output_tokens": self.max_output_tokens,
            "top_p": self.top_p,
            "top_k": self.top_k,
        }

class GeminiAPI:
    """Interface for the Gemini API."""
    
    def __init__(self, config: Config):
        """Initialize the API interface."""
        self.config = config
        self.model = genai.GenerativeModel(
            model_name=config.model_name,
            generation_config=config.get_generation_config()
        )
        
        # Rate limiting parameters
        self.rate_limit_encountered = False
        self.rate_limit_backoff = [5, 10, 30, 60, 120, 300, 600, 900, 1800, 3600]  # Up to 1 hour
        self.rate_limit_attempt = 0
        self.last_call_time = None
        self.min_call_interval = 5  # Minimum seconds between API calls
    
    def generate_text(self, prompt: str) -> Optional[str]:
        """Generate text from the API."""
        try:
            # Enforce minimum interval between API calls
            self._enforce_call_interval()
            
            # Generate response
            response = self.model.generate_content(prompt)
            
            # Reset rate limit flag if successful
            if self.rate_limit_encountered:
                self.rate_limit_encountered = False
                self.rate_limit_attempt = 0
            
            # Return the text
            return response.text if response else None
            
        except Exception as e:
            error_str = str(e).lower()
            
            # Check for rate limit errors
            if "rate limit" in error_str or "quota" in error_str:
                self.rate_limit_encountered = True
                self.rate_limit_attempt += 1
                
                if self.rate_limit_attempt < len(self.rate_limit_backoff):
                    backoff_time = self.rate_limit_backoff[self.rate_limit_attempt - 1]
                    logger.warning(f"Rate limit exceeded. Backing off for {backoff_time}s")
                    time.sleep(backoff_time)
                    
                    # Recursive retry after backoff
                    return self.generate_text(prompt)
            
            logger.error(f"Error generating text: {e}")
            return None
    
    def _enforce_call_interval(self) -> None:
        """Enforce minimum interval between API calls."""
        if self.last_call_time:
            elapsed = time.time() - self.last_call_time
            if elapsed < self.min_call_interval:
                sleep_time = self.min_call_interval - elapsed
                logger.debug(f"Sleeping for {sleep_time:.2f}s to respect API rate limits")
                time.sleep(sleep_time)
        
        self.last_call_time = time.time()

class CodeManager:
    """Manages code reading, writing, and analysis."""
    
    @staticmethod
    def read_code(filepath: Path) -> Optional[str]:
        """Read code from a file."""
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                return f.read()
        except Exception as e:
            logger.error(f"Failed to read code from {filepath}: {e}")
            return None
    
    @staticmethod
    def write_code(filepath: Path, code: str) -> bool:
        """Write code to a file."""
        try:
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(code)
            return True
        except Exception as e:
            logger.error(f"Failed to write code to {filepath}: {e}")
            return False
    
    @staticmethod
    def extract_version(code: str) -> str:
        """Extract version from code."""
        version_pattern = re.compile(r'VERSION\s*=\s*["\']([^"\']+)["\']')
        match = version_pattern.search(code)
        return match.group(1) if match else "unknown"

class AdaptaGen:
    """Main agent class that can modify itself."""
    
    def __init__(self, config: Config):
        """Initialize the agent."""
        self.config = config
        self.gemini_api = GeminiAPI(config)
        self.code_manager = CodeManager()
    
    def run(self, increment_type: str = 'revision', use_incremental: bool = False, 
            goal_name: str = None, max_components: int = 10, patient_mode: bool = False) -> None:
        """Run the agent."""
        logger.info(f"Running AdaptaGen {VERSION}")
        
        # This is a placeholder implementation
        # The actual implementation will be developed by the agent
        logger.info("This is a template implementation. The agent will develop itself.")
        
        # Example of generating text
        prompt = "Write a simple Python function to calculate the factorial of a number."
        response = self.gemini_api.generate_text(prompt)
        
        if response:
            logger.info("Successfully generated text from the API.")
            logger.info(f"Response: {response[:100]}...")
        else:
            logger.error("Failed to generate text from the API.")
    
    def list_versions(self) -> Dict[str, str]:
        """List all versions."""
        # This is a placeholder implementation
        return {VERSION: "current"}
    
    def generate_improvement_report(self) -> str:
        """Generate a report on improvements."""
        # This is a placeholder implementation
        return f"AdaptaGen {VERSION} - No improvements to report yet."

    def fix_version(self, target_version: str, use_incremental: bool = True, 
                  max_components: int = 5, patient_mode: bool = True) -> None:
        """
        Fix issues in another version of the agent.
        
        Args:
            target_version: The version to fix
            use_incremental: Whether to use incremental editing
            max_components: Maximum number of components to process
            patient_mode: Whether to use extended backoff times
        """
        logger.info(f"Attempting to fix version {target_version} using version {VERSION}")
        
        # Find the target version file
        target_file = None
        version_parts = target_version.split('.')
        if len(version_parts) != 3:
            logger.error(f"Invalid version format: {target_version}")
            return
            
        major = version_parts[0]
        minor = version_parts[1]
        
        # Handle revision if present
        if '-r' in version_parts[2]:
            patch_parts = version_parts[2].split('-r')
            patch = patch_parts[0]
            revision = patch_parts[1]
            target_filename = f"adaptagen_{major}_{minor}_{patch}_r{revision}.py"
        else:
            patch = version_parts[2]
            target_filename = f"adaptagen_{major}_{minor}_{patch}.py"
            
        target_file = Path(target_filename)
        
        if not target_file.exists():
            logger.error(f"Target version file not found: {target_file}")
            return
            
        # Read the target file
        target_code = self.code_manager.read_code(target_file)
        if not target_code:
            logger.error(f"Failed to read target file: {target_file}")
            return
            
        # Analyze the target code to identify issues
        try:
            from improvement_analyzer import ImprovementAnalyzer
            
            analyzer = ImprovementAnalyzer(target_file)
            if not analyzer.load_code():
                logger.error(f"Failed to analyze target file: {target_file}")
                return
                
            suggestions = analyzer.analyze()
            
            if not suggestions:
                logger.info(f"No improvement suggestions found for {target_version}")
                return
                
            # Get the top suggestions
            top_suggestions = analyzer.get_top_suggestions(limit=max_components)
            
            logger.info(f"Found {len(top_suggestions)} improvement suggestions for {target_version}")
            logger.info(analyzer.generate_report())
            
            # Create a backup of the target file
            backup_file = Path(f"{target_file}.bak")
            try:
                import shutil
                shutil.copy2(target_file, backup_file)
                logger.info(f"Created backup at {backup_file}")
            except Exception as e:
                logger.error(f"Failed to create backup: {e}")
                return
                
            # Fix each issue
            for i, suggestion in enumerate(top_suggestions):
                logger.info(f"Fixing issue {i+1}/{len(top_suggestions)}: {suggestion.description}")
                
                # Generate a prompt to fix the issue
                prompt = self._generate_fix_prompt(target_code, suggestion)
                
                # Generate improved code
                response = self.gemini_api.generate_text(prompt)
                
                if not response:
                    logger.warning(f"Failed to generate fix for {suggestion.description}")
                    continue
                    
                # Extract the code from the response
                improved_code = self._extract_code_from_response(response)
                
                if not improved_code:
                    logger.warning(f"Failed to extract code from response for {suggestion.description}")
                    continue
                    
                # Update the target code
                target_code = improved_code
                
                # Write the updated code to the target file
                if self.code_manager.write_code(target_file, target_code):
                    logger.info(f"Successfully applied fix for {suggestion.description}")
                else:
                    logger.error(f"Failed to write updated code to {target_file}")
                    self._restore_backup(backup_file, target_file)
                    return
                    
            logger.info(f"Successfully fixed {len(top_suggestions)} issues in {target_version}")
            
        except ImportError:
            logger.error("Failed to import ImprovementAnalyzer. Make sure improvement_analyzer.py is available.")
            return
        except Exception as e:
            logger.error(f"Error fixing version: {e}")
            if 'backup_file' in locals() and backup_file.exists():
                self._restore_backup(backup_file, target_file)
            return
            
    def _generate_fix_prompt(self, code: str, suggestion: ImprovementSuggestion) -> str:
        """
        Generate a prompt to fix an issue.
        
        Args:
            code: The code to fix
            suggestion: The improvement suggestion
            
        Returns:
            A prompt for the LLM
        """
        prompt = f"""
        You are an expert Python developer tasked with improving the following code.
        
        ISSUE TO FIX:
        Category: {suggestion.category}
        Description: {suggestion.description}
        Rationale: {suggestion.rationale}
        Component: {suggestion.component}
        
        CODE:
        ```python
        {code}
        ```
        
        Please provide an improved version of the code that addresses the issue.
        Focus specifically on fixing the identified issue while making minimal changes to other parts of the code.
        Return the complete improved code.
        """
        
        return prompt
        
    def _extract_code_from_response(self, response: str) -> Optional[str]:
        """
        Extract code from an LLM response.
        
        Args:
            response: The LLM response
            
        Returns:
            The extracted code, or None if no code was found
        """
        # Look for code blocks
        import re
        code_pattern = r"```(?:python)?\s*(.*?)```"
        matches = re.findall(code_pattern, response, re.DOTALL)
        
        if matches:
            return matches[0].strip()
            
        # If no code blocks found, check if the entire response is valid Python
        try:
            compile(response, '<string>', 'exec')
            return response.strip()
        except SyntaxError:
            pass
            
        return None
        
    def _restore_backup(self, backup_file: Path, target_file: Path) -> None:
        """
        Restore a file from backup.
        
        Args:
            backup_file: Path to the backup file
            target_file: Path to the target file
        """
        try:
            import shutil
            if backup_file.exists():
                shutil.copy2(backup_file, target_file)
                logger.info(f"Restored {target_file} from backup")
        except Exception as e:
            logger.error(f"Failed to restore from backup: {e}")

# If this script is run directly, it will just print a message
if __name__ == "__main__":
    print(f"This is the AdaptaGen template version {VERSION}.")
    print("Please use adaptagen_main.py to run the agent.") 
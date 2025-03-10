#!/usr/bin/env python3
"""
AdaptaGen: A self-modifying Python script using the Gemini API with version control.

Version: 0.0.1-r4
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
from typing import List, Dict, Optional, Any, Set, Type, ClassVar
from dataclasses import dataclass, field, asdict
import google.generativeai as genai
from dotenv import load_dotenv

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
VERSION = "0.0.1-r4"
VERSION_HISTORY_DIR = Path(".adaptagen_versions")
VERSION_METADATA_FILE = "version_metadata.json"

# Token control constants
TOKEN_PATTERN = r"<TOKEN:(\w+)>"
TOKEN_PREFIX = "<TOKEN:"
TOKEN_SUFFIX = ">"


class TokenRegistry:
    """Registry for managing tokens used throughout the codebase."""
    
    _registry: ClassVar[Dict[str, Any]] = {}
    _valid_tokens: ClassVar[Set[str]] = set()
    
    @classmethod
    def register(cls, token_name: str, value: Any) -> None:
        """Register a token with its value."""
        cls._registry[token_name] = value
        cls._valid_tokens.add(token_name)
    
    @classmethod
    def get(cls, token_name: str, default: Any = None) -> Any:
        """Get a token's value."""
        return cls._registry.get(token_name, default)
    
    @classmethod
    def is_valid(cls, token_name: str) -> bool:
        """Check if a token is valid."""
        return token_name in cls._valid_tokens
    
    @classmethod
    def list_tokens(cls) -> List[str]:
        """List all registered tokens."""
        return list(cls._registry.keys())
    
    @classmethod
    def format_token(cls, token_name: str) -> str:
        """Format a token name into a token string."""
        return f"{TOKEN_PREFIX}{token_name}{TOKEN_SUFFIX}"
    
    @classmethod
    def extract_tokens(cls, text: str) -> List[str]:
        """Extract all tokens from a text."""
        return re.findall(TOKEN_PATTERN, text)
    
    @classmethod
    def validate_tokens(cls, text: str) -> List[str]:
        """Validate tokens in a text and return invalid ones."""
        tokens = cls.extract_tokens(text)
        return [token for token in tokens if not cls.is_valid(token)]
    
    @classmethod
    def replace_tokens(cls, text: str) -> str:
        """Replace tokens in a text with their values."""
        for token in cls.extract_tokens(text):
            if cls.is_valid(token):
                token_str = cls.format_token(token)
                value = cls.get(token)
                if value is not None:
                    text = text.replace(token_str, str(value))
        return text


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
            return response.text
        except Exception as e:
            logger.error(f"Gemini API error: {e}")
            return None


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
    
    def run(self, increment_type: str = 'revision') -> None:
        """
        Execute the self-modification process.
        
        Args:
            increment_type: Type of version increment ('major', 'minor', 'patch', or 'revision')
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
        
        # Generate a prompt based on the current goal
        prompt = self.current_goal.get_prompt(current_code, self.config)
        
        # Get AI-generated improvements
        logger.info("Generating improved version using AI...")
        improved_code = self.gemini_api.generate_response(prompt)
        
        if not improved_code:
            logger.error("Failed to generate improved code.")
            return
        
        # Increment version and update in code
        new_version = self.version_manager.increment_version(VERSION, increment_type)
        improved_code = self.version_manager.update_version_in_code(improved_code, new_version)
        
        # Write the new version to a file
        new_filepath = Path(f"adaptagen_{new_version.replace('.', '_').replace('-', '_')}.py")
        if self.code_manager.write_code(new_filepath, improved_code):
            logger.info(f"New version {new_version} written to: {new_filepath}")
            
            # Save to version history
            self.version_control.save_version(improved_code, new_version)
        else:
            logger.error("Failed to write new version.")
    
    def list_versions(self) -> None:
        """List all versions in the version history."""
        versions = self.version_control.get_version_history()
        if not versions:
            logger.info("No version history found.")
            return
        
        logger.info("Version history:")
        for version in versions:
            logger.info(f"  - Version: {version['version']}, Timestamp: {version['timestamp']}, File: {version['filename']}")


def main():
    """Main entry point for the script."""
    try:
        # Register main function with token registry
        TokenRegistry.register("MAIN", "main")
        
        # Parse command line arguments
        if len(sys.argv) > 1:
            command = sys.argv[1]
            
            # Create config
            config = Config.from_env()
            adaptagen = AdaptaGen(config)
            
            if command == "list-versions":
                adaptagen.list_versions()
            elif command == "run":
                increment_type = sys.argv[2] if len(sys.argv) > 2 else 'revision'
                adaptagen.run(increment_type)
            elif command == "list-tokens":
                logger.info("Registered tokens:")
                for token in TokenRegistry.list_tokens():
                    value = TokenRegistry.get(token)
                    logger.info(f"  - {token}: {value}")
            else:
                logger.error(f"Unknown command: {command}")
                logger.info("Available commands: run, list-versions, list-tokens")
        else:
            # Default behavior
            config = Config.from_env()
            adaptagen = AdaptaGen(config)
            adaptagen.run()
    except ValueError as e:
        logger.error(e)
        sys.exit(1)
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main() 
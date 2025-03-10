#!/usr/bin/env python3
"""
AdaptaGen: A self-modifying Python script using the Gemini API with version control.

Version: 0.0.1-r1
"""

import os
import sys
import inspect
import logging
import tempfile
import json
import datetime
import hashlib
from pathlib import Path
from typing import List, Dict, Any, Optional, Callable, Tuple
from abc import ABC, abstractmethod
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
VERSION = "0.0.1-r1"
VERSION_HISTORY_DIR = ".adaptagen_versions"
VERSION_METADATA_FILE = "version_metadata.json"


class Config:
    """Manages configuration settings."""

    def __init__(self):
        load_dotenv()
        self.api_key = os.getenv(ENV_API_KEY)
        if not self.api_key:
            raise ValueError(f"{ENV_API_KEY} not found in environment variables.")
        genai.configure(api_key=self.api_key)
        self.model_name = os.getenv(ENV_MODEL_NAME, DEFAULT_MODEL_NAME)
        self.temperature = float(os.getenv(ENV_TEMPERATURE, DEFAULT_TEMPERATURE))
        self.max_output_tokens = int(os.getenv(ENV_MAX_OUTPUT_TOKENS, DEFAULT_MAX_OUTPUT_TOKENS))
        self.top_p = float(os.getenv(ENV_TOP_P, DEFAULT_TOP_P))
        self.top_k = int(os.getenv(ENV_TOP_K, DEFAULT_TOP_K))


class Goal(ABC):
    """Abstract base class for defining goals."""

    @abstractmethod
    def get_description(self) -> str:
        pass

    @abstractmethod
    def get_prompt(self, current_code: str) -> str:
        pass


class SelfEditGoal(Goal):
    """Goal for self-editing and improvement."""

    def get_description(self) -> str:
        return "Improve code structure, functionality, and robustness."

    def get_prompt(self, current_code: str) -> str:
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
        5. Maintain and improve the version control system.

        Return ONLY the improved code, directly executable.
        """


class GeminiAPI:
    """Interface for interacting with the Gemini API."""

    def __init__(self, config: Config):
        self.config = config
        self.model = genai.GenerativeModel(
            model_name=self.config.model_name,
            generation_config={
                "temperature": self.config.temperature,
                "max_output_tokens": self.config.max_output_tokens,
                "top_p": self.config.top_p,
                "top_k": self.config.top_k,
            }
        )

    def generate_response(self, prompt: str) -> Optional[str]:
        try:
            response = self.model.generate_content(prompt)
            return response.text
        except Exception as e:
            logger.error(f"Gemini API error: {e}")
            return None


class CodeManager:
    """Manages reading, writing, and versioning code."""

    @staticmethod
    def read_code(filepath: str) -> Optional[str]:
        """Read code from a file."""
        try:
            with open(filepath, 'r') as f:
                return f.read()
        except FileNotFoundError:
            logger.error(f"File not found: {filepath}")
        except Exception as e:
            logger.error(f"Error reading file: {e}")
        return None

    @staticmethod
    def write_code(filepath: str, code: str) -> bool:
        """Write code to a file."""
        try:
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

    @classmethod
    def setup_version_control(cls) -> None:
        """Set up version control directory if it doesn't exist."""
        if not os.path.exists(VERSION_HISTORY_DIR):
            try:
                os.makedirs(VERSION_HISTORY_DIR)
                logger.info(f"Created version history directory: {VERSION_HISTORY_DIR}")
                
                # Initialize metadata file
                metadata = {
                    "versions": [],
                    "latest_version": None
                }
                cls.write_metadata(metadata)
            except Exception as e:
                logger.error(f"Error setting up version control: {e}")

    @classmethod
    def write_metadata(cls, metadata: Dict) -> bool:
        """Write version metadata to file."""
        try:
            metadata_path = os.path.join(VERSION_HISTORY_DIR, VERSION_METADATA_FILE)
            with open(metadata_path, 'w') as f:
                json.dump(metadata, f, indent=2)
            return True
        except Exception as e:
            logger.error(f"Error writing metadata: {e}")
            return False

    @classmethod
    def read_metadata(cls) -> Dict:
        """Read version metadata from file."""
        try:
            metadata_path = os.path.join(VERSION_HISTORY_DIR, VERSION_METADATA_FILE)
            if os.path.exists(metadata_path):
                with open(metadata_path, 'r') as f:
                    return json.load(f)
            return {"versions": [], "latest_version": None}
        except Exception as e:
            logger.error(f"Error reading metadata: {e}")
            return {"versions": [], "latest_version": None}

    @classmethod
    def save_version(cls, code: str, version: str) -> bool:
        """Save a new version of the code."""
        try:
            cls.setup_version_control()
            
            # Calculate hash
            code_hash = cls.calculate_hash(code)
            
            # Create version filename
            timestamp = datetime.datetime.now().strftime("%Y%m%d%H%M%S")
            version_filename = f"adaptagen_{version.replace('.', '_').replace('-', '_')}_{timestamp}.py"
            version_path = os.path.join(VERSION_HISTORY_DIR, version_filename)
            
            # Save the code
            if cls.write_code(version_path, code):
                # Update metadata
                metadata = cls.read_metadata()
                version_info = {
                    "version": version,
                    "timestamp": timestamp,
                    "hash": code_hash,
                    "filename": version_filename,
                    "path": version_path
                }
                metadata["versions"].append(version_info)
                metadata["latest_version"] = version_info
                
                if cls.write_metadata(metadata):
                    logger.info(f"Saved version {version} to {version_path}")
                    return True
            
            return False
        except Exception as e:
            logger.error(f"Error saving version: {e}")
            return False

    @classmethod
    def get_version_history(cls) -> List[Dict]:
        """Get the version history."""
        metadata = cls.read_metadata()
        return metadata.get("versions", [])

    @classmethod
    def get_latest_version(cls) -> Optional[Dict]:
        """Get the latest version info."""
        metadata = cls.read_metadata()
        return metadata.get("latest_version")


class VersionManager:
    """Manages version control for the script."""
    
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
            return f"{major}.{minor}.{patch}-r{revision}"
        except Exception as e:
            logger.error(f"Error incrementing version: {e}")
            return f"{version}-r1"  # Fallback
    
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
        self.config = config
        self.gemini_api = GeminiAPI(config)
        self.code_manager = CodeManager()
        self.version_manager = VersionManager()
        self.current_goal = SelfEditGoal()

    def run(self, increment_type: str = 'revision') -> None:
        """
        Execute the self-modification process.
        
        Args:
            increment_type: Type of version increment ('major', 'minor', 'patch', or 'revision')
        """
        logger.info(f"Starting AdaptaGen {VERSION} with goal: {self.current_goal.get_description()}")
        
        # Read the current source code
        current_filepath = inspect.getfile(inspect.currentframe())
        current_code = self.code_manager.read_code(current_filepath)
        if not current_code:
            logger.error("Failed to read source code")
            return
        
        # Save current version to version history
        self.code_manager.save_version(current_code, VERSION)
        
        # Generate a prompt based on the current goal
        prompt = self.current_goal.get_prompt(current_code)
        
        # Get AI-generated improvements
        logger.info("Generating improved version using AI...")
        improved_code = self.gemini_api.generate_response(prompt)
        
        if not improved_code:
            logger.error("Failed to generate improved code")
            return
        
        # Increment version and update in code
        new_version = self.version_manager.increment_version(VERSION, increment_type)
        improved_code = self.version_manager.update_version_in_code(improved_code, new_version)
        
        # Write the new version to a file
        new_filepath = f"adaptagen_{new_version.replace('.', '_').replace('-', '_')}.py"
        if self.code_manager.write_code(new_filepath, improved_code):
            logger.info(f"New version {new_version} written to: {new_filepath}")
            
            # Save to version history
            self.code_manager.save_version(improved_code, new_version)
        else:
            logger.error("Failed to write new version")

    def list_versions(self) -> None:
        """List all versions in the version history."""
        versions = self.code_manager.get_version_history()
        if not versions:
            logger.info("No version history found")
            return
        
        logger.info("Version history:")
        for version in versions:
            logger.info(f"Version: {version['version']}, Timestamp: {version['timestamp']}, File: {version['filename']}")


def main():
    """Main entry point for the script."""
    try:
        # Parse command line arguments
        if len(sys.argv) > 1:
            command = sys.argv[1]
            if command == "list-versions":
                config = Config()
                adaptagen = AdaptaGen(config)
                adaptagen.list_versions()
                return
            elif command == "run":
                increment_type = sys.argv[2] if len(sys.argv) > 2 else 'revision'
                config = Config()
                adaptagen = AdaptaGen(config)
                adaptagen.run(increment_type)
                return
        
        # Default behavior
        config = Config()
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
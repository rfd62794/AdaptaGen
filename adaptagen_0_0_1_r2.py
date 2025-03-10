```python
#!/usr/bin/env python3
"""
AdaptaGen: A self-modifying Python script using the Gemini API with version control.

Version: 0.0.2-r0
"""

import os
import sys
import inspect
import logging
import json
import datetime
import hashlib
from pathlib import Path
from typing import List, Dict, Optional
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
VERSION = "0.0.1-r2"
VERSION_HISTORY_DIR = Path(".adaptagen_versions")
VERSION_METADATA_FILE = "version_metadata.json"

class Config:
    """Manages configuration settings."""

    def __init__(self):
        load_dotenv()
        self.api_key = os.getenv(ENV_API_KEY)
        if not self.api_key:
            raise ValueError(f"{ENV_API_KEY} not found in environment variables.")
        genai.configure(api_key=self.api_key)
        self.model = os.getenv(ENV_MODEL_NAME, DEFAULT_MODEL_NAME)
        self.temperature = float(os.getenv(ENV_TEMPERATURE, DEFAULT_TEMPERATURE))
        self.max_output_tokens = int(os.getenv(ENV_MAX_OUTPUT_TOKENS, DEFAULT_MAX_OUTPUT_TOKENS))
        self.top_p = float(os.getenv(ENV_TOP_P, DEFAULT_TOP_P))
        self.top_k = int(os.getenv(ENV_TOP_K, DEFAULT_TOP_K))

    def get_generation_config(self):
        return {
            "temperature": self.temperature,
            "max_output_tokens": self.config.max_output_tokens,
            "top_p": self.top_p,
            "top_k": self.top_k,
        }


class Goal:
    """Base class for defining goals."""

    description: str = "No description provided"

    def get_prompt(self, current_code: str) -> str:
        raise NotImplementedError


class SelfEditGoal(Goal):
    """Goal for self-editing and improvement."""

    description = "Improve code structure, functionality, and robustness."

    def get_prompt(self, current_code: str) -> str:
        return f"""
        Improve the following Python script:

        ```python
        {current_code}
        ```

        Focus on:
        - SOLID, DRY, PEP 8, and KISS principles.
        - Enhanced self-modification capabilities.
        - Robustness and error handling.
        - Useful features aligned with its purpose.
        - Maintain and improve the version control system.

        Return ONLY the improved code, directly executable.
        """


class GeminiAPI:
    """Interface for interacting with the Gemini API."""

    def __init__(self, config: Config):
        self.model = genai.GenerativeModel(model=config.model, generation_config=config.get_generation_config())

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
    def read_code(filepath: Path) -> Optional[str]:
        try:
            with open(filepath, 'r') as f:
                return f.read()
        except FileNotFoundError:
            logger.error(f"File not found: {filepath}")
        except Exception as e:
            logger.error(f"Error reading file: {e}")
        return None

    @staticmethod
    def write_code(filepath: Path, code: str) -> bool:
        try:
            with open(filepath, 'w') as f:
                f.write(code)
            return True
        except Exception as e:
            logger.error(f"Error writing file: {e}")
            return False

    @staticmethod
    def calculate_hash(code: str) -> str:
        return hashlib.sha256(code.encode()).hexdigest()

    @staticmethod
    def extract_version(code: str) -> str:
        for line in code.splitlines():
            if line.startswith('VERSION = '):
                return line.split('=')[1].strip().strip('"\'')
        return "unknown"


class VersionControl:
    """Manages version control."""

    def __init__(self, directory: Path, metadata_file: str):
        self.directory = directory
        self.metadata_file = metadata_file
        self.directory.mkdir(parents=True, exist_ok=True)

    def get_metadata_path(self) -> Path:
        return self.directory / self.metadata_file

    def read_metadata(self) -> Dict:
        try:
            with open(self.get_metadata_path(), 'r') as f:
                return json.load(f)
        except FileNotFoundError:
            return {"versions": [], "latest_version": None}
        except json.JSONDecodeError:
            logger.error("Corrupted metadata file.")
            return {"versions": [], "latest_version": None}


    def write_metadata(self, metadata: Dict) -> None:
        with open(self.get_metadata_path(), 'w') as f:
            json.dump(metadata, f, indent=2)

    def save_version(self, code: str, version: str) -> None:
        code_hash = CodeManager.calculate_hash(code)
        timestamp = datetime.datetime.now().strftime("%Y%m%d%H%M%S")
        version_filename = f"adaptagen_{version.replace('.', '_').replace('-', '_')}_{timestamp}.py"
        version_path = self.directory / version_filename
        CodeManager.write_code(version_path, code)

        metadata = self.read_metadata()
        version_info = {
            "version": version,
            "timestamp": timestamp,
            "hash": code_hash,
            "filename": version_filename,
            "path": str(version_path)  # Store as string for JSON serialization
        }
        metadata["versions"].append(version_info)
        metadata["latest_version"] = version_info
        self.write_metadata(metadata)
        logger.info(f"Saved version {version} to {version_path}")

    def get_version_history(self) -> List[Dict]:
        metadata = self.read_metadata()
        return metadata.get("versions", [])

    def get_latest_version(self) -> Optional[Dict]:
        metadata = self.read_metadata()
        return metadata.get("latest_version")


class VersionManager:
    """Manages version string manipulation."""

    @staticmethod
    def increment_version(version: str, increment_type: str = 'revision') -> str:
        try:
            parts = version.split('-r')
            version_part = parts[0].split('.')
            revision = int(parts[1]) if len(parts) > 1 else 0

            if increment_type == 'major':
                version_part[0] = str(int(version_part[0]) + 1)
                version_part[1:] = ['0', '0']
                revision = 0
            elif increment_type == 'minor':
                version_part[1] = str(int(version_part[1]) + 1)
                version_part[2] = '0'
                revision = 0
            elif increment_type == 'patch':
                version_part[2] = str(int(version_part[2]) + 1)
                revision = 0
            else:
                revision += 1

            return f"{'.'.join(version_part)}-r{revision}"

        except Exception as e:
            logger.error(f"Error incrementing version: {e}")
            return f"{version}-r1"

    @staticmethod
    def update_version_in_code(code: str, new_version: str) -> str:
        lines = code.splitlines()
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
        self.version_control = VersionControl(VERSION_HISTORY_DIR, VERSION_METADATA_FILE)
        self.version_manager = VersionManager()
        self.current_goal = SelfEditGoal()

    def run(self, increment_type: str = 'revision') -> None:
        logger.info(f"Starting AdaptaGen with goal: {self.current_goal.description}")

        current_filepath = Path(inspect.getfile(inspect.currentframe()))
        current_code = self.code_manager.read_code(current_filepath)
        if not current_code:
            logger.error("Failed to read source code.")
            return

        self.version_control.save_version(current_code, VERSION)

        prompt = self.current_goal.get_prompt(current_code)

        logger.info("Generating improved version using AI...")
        improved_code = self.gemini_api.generate_response(prompt)

        if not improved_code:
            logger.error("Failed to generate improved code.")
            return

        new_version = self.version_manager.increment_version(VERSION, increment_type)
        improved_code = self.version_manager.update_version_in_code(improved_code, new_version)

        new_filepath = Path(f"adaptagen_{new_version.replace('.', '_').replace('-', '_')}.py")
        if self.code_manager.write_code(new_filepath, improved_code):
            logger.info(f"New version {new_version} written to: {new_filepath}")
            self.version_control.save_version(improved_code, new_version)
        else:
            logger.error("Failed to write new version.")

    def list_versions(self) -> None:
        versions = self.version_control.get_version_history()
        if not versions:
            logger.info("No version history found.")
            return

        logger.info("Version history:")
        for version in versions:
            logger.info(f"  - Version: {version['version']}, Timestamp: {version['timestamp']}, File: {version['filename']}")



def main():
    try:
        config = Config()
        adaptagen = AdaptaGen(config)

        if len(sys.argv) > 1:
            command = sys.argv[1]
            if command == "list-versions":
                adaptagen.list_versions()
            elif command == "run":
                increment_type = sys.argv[2] if len(sys.argv) > 2 else 'revision'
                adaptagen.run(increment_type)
            else:
                print(f"Unknown command: {command}")
        else:
            adaptagen.run()

    except ValueError as e:
        logger.error(e)
        sys.exit(1)
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
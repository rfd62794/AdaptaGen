#!/usr/bin/env python3
"""
AdaptaGen: A self-modifying Python script using the Gemini API.
"""

import os
import sys
import inspect
import logging
from typing import List, Dict, Any, Optional, Callable
from abc import ABC, abstractmethod
import google.generativeai as genai
from dotenv import load_dotenv

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Constants
ENV_API_KEY = "GEMINI_API_KEY"
ENV_MODEL_NAME = "GEMINI_MODEL"
DEFAULT_MODEL_NAME = "gemini-1.5-pro"
ENV_TEMPERATURE = "TEMPERATURE"
DEFAULT_TEMPERATURE = 0.7
ENV_MAX_OUTPUT_TOKENS = "MAX_OUTPUT_TOKENS"
DEFAULT_MAX_OUTPUT_TOKENS = 8192
ENV_TOP_P = "TOP_P"
DEFAULT_TOP_P = 0.95
ENV_TOP_K = "TOP_K"
DEFAULT_TOP_K = 40
NEW_VERSION_SUFFIX = "new"


class Config:
    """Manages configuration settings."""

    def __init__(self):
        load_dotenv()
        self.api_key = os.getenv(ENV_API_KEY)
        if not self.api_key:
            logger.error(f"{ENV_API_KEY} not found in environment variables.")
            sys.exit(1)
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

        Return ONLY the improved code, directly executable.
        """


class GeminiAPI:
    """Interface for interacting with the Gemini API."""

    def __init__(self, config: Config):
        self.model = genai.GenerativeModel(
            model_name=config.model_name,
            generation_config={
                "temperature": config.temperature,
                "max_output_tokens": config.max_output_tokens,
                "top_p": config.top_p,
                "top_k": config.top_k,
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
    """Manages reading and writing code."""

    @staticmethod
    def read_code(filepath: str) -> Optional[str]:
        try:
            with open(filepath, 'r') as f:
                return f.read()
        except FileNotFoundError:
            logger.error(f"File not found: {filepath}")
            return None
        except Exception as e:
            logger.error(f"Error reading file: {e}")
            return None

    @staticmethod
    def write_code(filepath: str, code: str) -> bool:
        try:
            with open(filepath, 'w') as f:
                f.write(code)
            return True
        except Exception as e:
            logger.error(f"Error writing file: {e}")
            return False


class AdaptaGen:
    """Orchestrates the self-modification process."""

    def __init__(self, config: Config):
        self.config = config
        self.gemini_api = GeminiAPI(config)
        self.code_manager = CodeManager()
        self.current_goal = SelfEditGoal()

    def run(self):
        current_filepath = inspect.getfile(inspect.currentframe())
        current_code = self.code_manager.read_code(current_filepath)
        if not current_code:
            return

        prompt = self.current_goal.get_prompt(current_code)
        improved_code = self.gemini_api.generate_response(prompt)
        if not improved_code:
            return

        new_filepath = f"{os.path.splitext(current_filepath)[0]}_{NEW_VERSION_SUFFIX}.py"
        if self.code_manager.write_code(new_filepath, improved_code):
            logger.info(f"New version written to: {new_filepath}")


def main():
    config = Config()
    adaptagen = AdaptaGen(config)
    adaptagen.run()


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
AdaptaGen: A self-modifying Python script using the Gemini API.

This script can read its own source code and generate new versions of itself
based on internal goals. The initial goal is to make controlled edits to itself.
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
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class ConfigManager:
    """Manages configuration settings for the application."""
    
    def __init__(self):
        """Initialize configuration settings from environment variables."""
        # Load environment variables from .env file if it exists
        load_dotenv()
        
        # Get API key from environment variable
        self.api_key = os.getenv("GEMINI_API_KEY")
        if not self.api_key:
            logger.error("GEMINI_API_KEY not found in environment variables")
            sys.exit(1)
        
        # Configure the Gemini API
        genai.configure(api_key=self.api_key)
        
        # Default model configuration
        self.model_name = os.getenv("GEMINI_MODEL", "gemini-1.5-pro")
        self.temperature = float(os.getenv("TEMPERATURE", "0.7"))
        self.max_output_tokens = int(os.getenv("MAX_OUTPUT_TOKENS", "8192"))
        self.top_p = float(os.getenv("TOP_P", "0.95"))
        self.top_k = int(os.getenv("TOP_K", "40"))


class Goal(ABC):
    """Abstract base class for defining goals for self-modification."""
    
    @abstractmethod
    def get_description(self) -> str:
        """Return a description of the goal."""
        pass
    
    @abstractmethod
    def get_prompt(self, current_code: str) -> str:
        """Generate a prompt for the AI based on the current code and this goal."""
        pass


class SelfEditGoal(Goal):
    """Goal focused on making controlled edits to the script itself."""
    
    def get_description(self) -> str:
        """Return a description of the self-editing goal."""
        return "Make controlled edits to improve the script's structure and functionality"
    
    def get_prompt(self, current_code: str) -> str:
        """Generate a prompt for self-editing."""
        return f"""
        You are analyzing a Python script that can modify itself using the Gemini API.
        
        Here is the current code:
        
        ```python
        {current_code}
        ```
        
        Your task is to suggest improvements to this code that would:
        1. Enhance its structure following SOLID, DRY, PEP 8, and KISS principles
        2. Improve its self-modification capabilities
        3. Make it more robust and error-resistant
        4. Add useful features that align with its purpose
        
        Return ONLY the complete improved version of the code with no additional explanations.
        The code should be directly executable.
        """


class AIModelInterface:
    """Interface for interacting with the Gemini AI model."""
    
    def __init__(self, config_manager: ConfigManager):
        """Initialize the AI model interface with configuration."""
        self.config = config_manager
        self.model = genai.GenerativeModel(
            model_name=self.config.model_name,
            generation_config={
                "temperature": self.config.temperature,
                "max_output_tokens": self.config.max_output_tokens,
                "top_p": self.config.top_p,
                "top_k": self.config.top_k,
            }
        )
    
    def generate_response(self, prompt: str) -> str:
        """Generate a response from the AI model based on the given prompt."""
        try:
            response = self.model.generate_content(prompt)
            return response.text
        except Exception as e:
            logger.error(f"Error generating AI response: {e}")
            return ""


class CodeReader:
    """Reads and processes the script's own source code."""
    
    @staticmethod
    def get_own_source_code() -> str:
        """Read the source code of the current script."""
        try:
            # Get the filename of the current script
            current_file = inspect.getfile(inspect.currentframe())
            with open(current_file, 'r') as file:
                return file.read()
        except Exception as e:
            logger.error(f"Error reading own source code: {e}")
            return ""


class CodeWriter:
    """Writes new versions of the script."""
    
    @staticmethod
    def write_new_version(new_code: str, version_suffix: str = "new") -> bool:
        """Write a new version of the script to a file."""
        try:
            # Get the filename of the current script
            current_file = inspect.getfile(inspect.currentframe())
            file_name, file_ext = os.path.splitext(current_file)
            
            # Create a new filename with a version suffix
            new_file = f"{file_name}_{version_suffix}{file_ext}"
            
            with open(new_file, 'w') as file:
                file.write(new_code)
            
            logger.info(f"New version written to {new_file}")
            return True
        except Exception as e:
            logger.error(f"Error writing new version: {e}")
            return False


class AdaptaGen:
    """Main class that orchestrates the self-modification process."""
    
    def __init__(self):
        """Initialize the AdaptaGen system."""
        self.config_manager = ConfigManager()
        self.ai_interface = AIModelInterface(self.config_manager)
        self.code_reader = CodeReader()
        self.code_writer = CodeWriter()
        self.current_goal = SelfEditGoal()  # Start with the self-editing goal
    
    def run(self):
        """Execute the self-modification process."""
        logger.info(f"Starting AdaptaGen with goal: {self.current_goal.get_description()}")
        
        # Read the current source code
        current_code = self.code_reader.get_own_source_code()
        if not current_code:
            logger.error("Failed to read source code")
            return
        
        # Generate a prompt based on the current goal
        prompt = self.current_goal.get_prompt(current_code)
        
        # Get AI-generated improvements
        logger.info("Generating improved version using AI...")
        improved_code = self.ai_interface.generate_response(prompt)
        
        if not improved_code:
            logger.error("Failed to generate improved code")
            return
        
        # Write the new version
        success = self.code_writer.write_new_version(improved_code)
        if success:
            logger.info("Successfully created new version of the script")
        else:
            logger.error("Failed to write new version")


def main():
    """Main entry point for the script."""
    try:
        adapta_gen = AdaptaGen()
        adapta_gen.run()
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main() 
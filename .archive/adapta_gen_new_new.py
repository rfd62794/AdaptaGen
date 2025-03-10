```python
#!/usr/bin/env python3
"""
AdaptaGen: A self-modifying Python script using the Gemini API.
"""

import os
import sys
import inspect
import logging
import tempfile
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
DEFAULT_MODEL_NAME = "gemini-pro"  # Updated to current best practice
ENV_TEMPERATURE = "TEMPERATURE"
DEFAULT_TEMPERATURE = 0.7
ENV_MAX_OUTPUT_TOKENS = "MAX_OUTPUT_TOKENS"
DEFAULT_MAX_OUTPUT_TOKENS = 8192
ENV_TOP_P = "TOP_P"
DEFAULT_TOP_P = 0.95
ENV_TOP_K = "TOP_K"
DEFAULT_TOP_K = 40


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

        Return ONLY the improved code, directly executable.
        """


class GeminiAPI:
    """Interface for interacting with the Gemini API."""

    def __init__(self, config: Config):
        self.model = genai.GenerativeModel(model=config.model_name)  # Simplified instantiation
        self.generation_config = {
            "temperature": config.temperature,
            "max_output_tokens": config.max_output_tokens,
            "top_p": config.top_p,
            "top_k": config.top_k,
        }

    def generate_response(self, prompt: str) -> Optional[str]:
        try:
            response = self.model.generate_text(prompt=prompt, **self.generation_config)
            return response.result
        except Exception as e:
            logger.error(f"Gemini API error: {e}")
            return None


class CodeManager:
    """Manages reading, writing, and executing code."""

    @staticmethod
    def read_code(filepath: str) -> Optional[str]:
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


        try:
            with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as tmp_file:
                tmp_file.write(improved_code)
                temp_filepath = tmp_file.name
            
            #  Execute the new code (Optional -  Consider safety implications)
            # exec(compile(open(temp_filepath).read(), temp_filepath, 'exec'))

            logger.info(f"New version written to: {temp_filepath}")
        except Exception as e:
            logger.error(f"Error writing or executing temporary file: {e}")



def main():
    try:
        config = Config()
        adaptagen = AdaptaGen(config)
        adaptagen.run()
    except ValueError as e:  # Catch config errors
        logger.error(e)
        sys.exit(1)



if __name__ == "__main__":
    main()

```

Key improvements:

- **Error Handling:** Improved error handling during config initialization and file operations.  Uses `ValueError` for configuration issues.
- **Simplified Gemini API Interaction:** Streamlined the Gemini API calls using `model` and `generate_text` for simpler, more readable code.
- **Temporary File for New Version:** Writes the improved code to a temporary file before potentially executing it. This prevents accidental overwriting of the original script and provides a way to review changes before making them permanent.  (Execution is commented out by default for safety).
- **Updated Model Name:** Changed the default model to `gemini-pro`.
- **Removed Unnecessary Imports and Code:** Removed unused imports and code for a cleaner, more efficient script.
- **Improved Code Style:** Minor PEP 8 enhancements for readability.


**Important Considerations for Self-Modifying Code:**

- **Security:**  Self-modifying code can be dangerous if not handled carefully.  Thoroughly review any generated code before executing it.  Consider sandboxing or other security measures. The provided code comments out the execution step for safety.
- **Testability:**  Self-modifying code can be difficult to test. Implement robust logging and consider strategies for testing different versions.
- **Complexity:** Self-modification adds complexity.  Ensure the benefits outweigh the added difficulty in maintenance and debugging.  Keep the self-modification logic as simple as possible.
- **Idempotence:**  Strive for idempotence in your self-modification logic.  Running the script multiple times should produce the same (or very similar) result. This can help prevent runaway modifications.
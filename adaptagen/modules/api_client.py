"""
API Client Module - Handles interactions with the Gemini API.
"""

import time
import logging
import re
from typing import Optional, Dict, Any

import google.generativeai as genai

# Configure logging
logger = logging.getLogger(__name__)

class GeminiAPI:
    """Handles interactions with the Gemini API."""
    
    def __init__(self, config):
        """
        Initialize the Gemini API client.
        
        Args:
            config: Configuration object with API settings
        """
        self.config = config
        self.last_call_time = 0
        self.min_call_interval = 1  # Minimum interval between API calls in seconds
        
        # Configure the API
        genai.configure(api_key=config.api_key)
        
        # Initialize the model
        self.model = genai.GenerativeModel(
            model_name=config.model_name,
            generation_config=config.get_generation_config()
        )
        
        logger.info(f"Initialized Gemini API with model: {config.model_name}")
        
    def generate_response(self, prompt: str) -> Optional[str]:
        """
        Generate a response from the Gemini API.
        
        Args:
            prompt: The prompt to send to the API
            
        Returns:
            The generated response or None if an error occurred
        """
        # Enforce minimum interval between API calls
        self._enforce_call_interval()
        
        try:
            logger.info("Sending request to Gemini API...")
            
            # Record the time of this call
            self.last_call_time = time.time()
            
            # Generate the response
            response = self.model.generate_content(prompt)
            
            if not response or not response.text:
                logger.warning("Empty response from Gemini API")
                return None
                
            # Extract the text from the response
            generated_text = response.text
            
            # Fix any incomplete code
            fixed_text = self._fix_incomplete_code(generated_text)
            
            logger.info(f"Received response from Gemini API ({len(fixed_text)} characters)")
            return fixed_text
            
        except Exception as e:
            # Handle rate limit errors
            if "429" in str(e) or "rate limit" in str(e).lower():
                logger.warning(f"Rate limit exceeded: {e}")
                
                # Extract wait time if available
                wait_time = 10  # Default wait time in seconds
                time_match = re.search(r'(\d+)\s*second', str(e))
                if time_match:
                    wait_time = int(time_match.group(1))
                    
                logger.info(f"Waiting for {self._format_time(wait_time)} before retrying...")
                time.sleep(wait_time)
                
                # Retry the request
                return self.generate_response(prompt)
            else:
                logger.error(f"Error generating response: {e}")
                return None
                
    def _enforce_call_interval(self) -> None:
        """Enforce minimum interval between API calls to avoid rate limits."""
        if self.last_call_time > 0:
            elapsed = time.time() - self.last_call_time
            if elapsed < self.min_call_interval:
                wait_time = self.min_call_interval - elapsed
                logger.debug(f"Waiting {wait_time:.2f}s between API calls")
                time.sleep(wait_time)
                
    def _format_time(self, seconds: int) -> str:
        """Format time in seconds to a human-readable string."""
        if seconds < 60:
            return f"{seconds} seconds"
        elif seconds < 3600:
            return f"{seconds // 60} minutes {seconds % 60} seconds"
        else:
            return f"{seconds // 3600} hours {(seconds % 3600) // 60} minutes"
            
    def _fix_incomplete_code(self, code: str) -> str:
        """
        Fix incomplete code in the response.
        
        Args:
            code: The code to fix
            
        Returns:
            Fixed code
        """
        # Check for unclosed triple quotes
        triple_quote_count = code.count('"""')
        if triple_quote_count % 2 != 0:
            # Add closing triple quotes
            code += '\n"""'
            
        # Check for unclosed code blocks
        code_block_starts = code.count("```python")
        code_block_ends = code.count("```") - code_block_starts
        
        if code_block_starts > code_block_ends:
            # Add missing closing code blocks
            code += "\n```"
            
        # Check for unclosed parentheses, brackets, and braces
        open_chars = {'(': ')', '[': ']', '{': '}'}
        char_stack = []
        
        for char in code:
            if char in open_chars:
                char_stack.append(char)
            elif char in open_chars.values():
                expected_char = None
                if char_stack:
                    open_char = char_stack.pop()
                    expected_char = open_chars.get(open_char)
                    
                if expected_char != char:
                    # Mismatched closing character, but we'll continue checking
                    pass
                    
        # Add any missing closing characters
        while char_stack:
            open_char = char_stack.pop()
            code += open_chars.get(open_char, '')
            
        return code
        
    def generate_text(self, prompt: str) -> Optional[str]:
        """
        Generate text from the Gemini API (simplified version of generate_response).
        
        Args:
            prompt: The prompt to send to the API
            
        Returns:
            The generated text or None if an error occurred
        """
        # Enforce minimum interval between API calls
        self._enforce_call_interval()
        
        try:
            # Record the time of this call
            self.last_call_time = time.time()
            
            # Generate the response
            response = self.model.generate_content(prompt)
            
            if not response or not response.text:
                return None
                
            return response.text
            
        except Exception as e:
            # Handle rate limit errors
            if "429" in str(e) or "rate limit" in str(e).lower():
                logger.warning(f"Rate limit exceeded: {e}")
                
                # Extract wait time if available
                wait_time = 10  # Default wait time in seconds
                time_match = re.search(r'(\d+)\s*second', str(e))
                if time_match:
                    wait_time = int(time_match.group(1))
                    
                logger.info(f"Waiting for {self._format_time(wait_time)} before retrying...")
                time.sleep(wait_time)
                
                # Retry the request
                return self.generate_text(prompt)
            else:
                logger.error(f"Error generating text: {e}")
                return None 
"""
Configuration Module - Manages configuration settings for AdaptaGen.
"""

import os
import logging
from dataclasses import dataclass, field, asdict
from typing import Dict, Any

import google.generativeai as genai
from dotenv import load_dotenv

from adaptagen.modules.token_system import TokenRegistry

# Configure logging
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
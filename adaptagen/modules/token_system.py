"""
Token Management Module - Handles token registration and replacement throughout the codebase.
"""

import re
from typing import Any, Dict, List, ClassVar
from dataclasses import dataclass

# Token control constants
TOKEN_PATTERN = r"<TOKEN:(\w+)>"
TOKEN_PREFIX = "<TOKEN:"
TOKEN_SUFFIX = ">"

@dataclass
class Token:
    """Represents a token with a name and value."""
    name: str
    value: Any

class TokenRegistry:
    """Registry for managing tokens used throughout the codebase."""

    _registry: ClassVar[Dict[str, Token]] = {}

    @classmethod
    def register(cls, name: str, value: Any) -> None:
        """Register a token with its value."""
        cls._registry[name] = Token(name, value)

    @classmethod
    def get(cls, name: str, default: Any = None) -> Any:
        """Get a token's value."""
        token = cls._registry.get(name)
        return token.value if token else default

    @classmethod
    def format_token(cls, name: str) -> str:
        """Format a token name into a token string."""
        return f"{TOKEN_PREFIX}{name}{TOKEN_SUFFIX}"

    @classmethod
    def validate_tokens(cls, text: str) -> List[str]:
        """Validates tokens in a text and returns a list of invalid tokens."""
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
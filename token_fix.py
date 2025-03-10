"""
Simple script to demonstrate the fix for NAME token validation.
"""

import re
from typing import List, Dict, Any, ClassVar
from dataclasses import dataclass

# Token control constants
TOKEN_PATTERN = r"<TOKEN:(\w+)>"
TOKEN_PREFIX = "<TOKEN:"
TOKEN_SUFFIX = ">"

@dataclass
class Token:
    name: str
    value: Any

class TokenRegistry:
    """Registry for managing tokens used throughout the codebase."""

    _registry: ClassVar[Dict[str, Token]] = {}

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
        """Formats a token name into a token string."""
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
        """Replaces tokens in a text with their values."""
        for token in cls._registry.values():
            text = text.replace(cls.format_token(token.name), str(token.value))
        return text

def main():
    # Register some tokens
    TokenRegistry.register("TEST", "test_value")
    TokenRegistry.register("VERSION", "1.0.0")
    
    # Test text with valid, invalid, and NAME tokens
    test_text = """
    This is a test with valid token: <TOKEN:TEST>
    This is a test with invalid token: <TOKEN:INVALID>
    This is a test with NAME token: <TOKEN:NAME>
    This is a test with VERSION token: <TOKEN:VERSION>
    """
    
    # Validate tokens
    invalid_tokens = TokenRegistry.validate_tokens(test_text)
    print(f"Invalid tokens: {invalid_tokens}")
    
    # Replace tokens
    replaced_text = TokenRegistry.replace_tokens(test_text)
    print("\nReplaced text:")
    print(replaced_text)

if __name__ == "__main__":
    main() 
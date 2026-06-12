"""
Base abstract service class for LLM provider communication.

All providers must inherit from BaseLLMService and implement the
generate_response() generator method. This allows both unary and
streaming consumers to work identically with any provider.

The generator yields:
  - str: individual content tokens/chunks
  - dict: final chunk with usage metadata (e.g., {"usage": {...}})
"""

from abc import ABC, abstractmethod
from typing import Generator, Union


class BaseLLMService(ABC):
    """
    Abstract base class for LLM provider integrations.

    Every provider service must implement generate_response() as a
    generator that yields strings (tokens) and optionally a final
    dict with usage information.
    """

    provider_name: str = ""

    def __init__(self, api_key: str, base_url: str | None = None):
        """
        Initialize the provider service.

        Args:
            api_key: The API key for the provider.
            base_url: Optional base URL override (for compatible providers).
        """
        self.api_key = api_key
        self.base_url = base_url

    @abstractmethod
    def generate_response(
        self,
        model: str,
        messages: list[dict],
        max_tokens: int = 1024,
        temperature: float = 0.7,
    ) -> Generator[Union[str, dict], None, None]:
        """
        Generate a response from the LLM provider.

        Args:
            model: The model identifier (e.g., "gpt-4", "claude-3-opus").
            messages: List of message dicts with "role" and "content".
            max_tokens: Maximum tokens to generate.
            temperature: Sampling temperature (0.0 to 2.0).

        Yields:
            str: Each token/chunk of the response.
            dict: Final chunk with {"usage": {"prompt_tokens": int, "completion_tokens": int}}
        """
        raise NotImplementedError

    def validate_config(self) -> bool:
        """
        Validate that the provider is properly configured.

        Returns True if configuration is valid, raises ValueError otherwise.
        """
        if not self.api_key:
            raise ValueError(f"{self.provider_name}: API key is not configured")
        return True

    def _build_headers(self) -> dict:
        """Build standard headers for HTTP requests to the provider."""
        return {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
        }
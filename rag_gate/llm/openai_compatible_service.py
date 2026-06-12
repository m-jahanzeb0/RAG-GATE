"""
OpenAI-compatible provider implementation for RAG-Gate.

Supports any API that implements the OpenAI-compatible chat completions
endpoint. This includes:
  - Groq (api.groq.com)
  - OpenRouter (openrouter.ai)
  - Together AI (api.together.xyz)
  - Perplexity (api.perplexity.ai)
  - Local models (via Ollama, vLLM, etc.)

Uses the openai Python SDK with a custom base_url.
"""

import logging
from typing import Generator, Union

from openai import OpenAI
from openai import APIError as OpenAIAPIError

from .base import BaseLLMService

logger = logging.getLogger(__name__)


class OpenAICompatibleService(BaseLLMService):
    """
    Generic OpenAI-compatible provider service.

    Works with any API that exposes an OpenAI-compatible /chat/completions endpoint.
    Users pass the base_url to point to their provider of choice.
    """

    provider_name = "openai-compatible"

    def __init__(self, api_key: str, base_url: str | None = None):
        """
        Initialize with an API key and a custom base URL.

        Args:
            api_key: The API key for the compatible provider.
            base_url: The base URL of the compatible API endpoint.
                     Must be provided for this service to function.
        """
        if not base_url:
            raise ValueError(
                "OpenAI-compatible provider requires a base_url. "
                "Set DEFAULT_OPENAI_COMPATIBLE_BASE_URL in your .env"
            )
        super().__init__(api_key, base_url)
        self.client = OpenAI(api_key=api_key, base_url=base_url)

    def generate_response(
        self,
        model: str,
        messages: list[dict],
        max_tokens: int = 1024,
        temperature: float = 0.7,
    ) -> Generator[Union[str, dict], None, None]:
        """
        Generate a response from an OpenAI-compatible provider.

        Uses the same streaming approach as OpenAIService.
        """
        self.validate_config()

        try:
            response = self.client.chat.completions.create(
                model=model,
                messages=messages,
                max_tokens=max_tokens,
                temperature=temperature,
                stream=True,
                stream_options={"include_usage": True},
            )

            for chunk in response:
                if chunk.choices and len(chunk.choices) > 0:
                    delta = chunk.choices[0].delta
                    if delta and delta.content:
                        yield delta.content

                # Handle usage information if available
                if hasattr(chunk, "usage") and chunk.usage:
                    usage_data = {
                        "prompt_tokens": chunk.usage.prompt_tokens or 0,
                        "completion_tokens": chunk.usage.completion_tokens or 0,
                    }
                    yield {"usage": usage_data}

        except OpenAIAPIError as e:
            logger.error("OpenAI-compatible API error (%s): %s", self.base_url, e)
            raise

    def validate_config(self) -> bool:
        """Validate the compatible provider configuration."""
        if not self.api_key:
            raise ValueError(
                f"OpenAI-compatible provider ({self.base_url}): API key is not configured"
            )
        if not self.base_url:
            raise ValueError(
                "OpenAI-compatible provider: base_url is required"
            )
        return True
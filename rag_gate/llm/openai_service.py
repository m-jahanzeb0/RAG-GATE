"""
OpenAI provider implementation for RAG-Gate.

Uses the official openai Python SDK to generate responses.
Supports both streaming and non-streaming modes via a unified generator.
"""

import logging
from typing import Generator, Union

from openai import OpenAI
from openai import APIError as OpenAIAPIError

from .base import BaseLLMService

logger = logging.getLogger(__name__)


class OpenAIService(BaseLLMService):
    """OpenAI LLM provider service."""

    provider_name = "openai"

    def __init__(self, api_key: str, base_url: str | None = None):
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
        Generate a response from OpenAI.

        Always requests a stream from the API. If the consumer (view)
        wants unary mode, it collects all tokens. If it wants streaming,
        it yields them directly.
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

                # Handle usage information (only in the final chunk)
                if hasattr(chunk, "usage") and chunk.usage:
                    usage_data = {
                        "prompt_tokens": chunk.usage.prompt_tokens or 0,
                        "completion_tokens": chunk.usage.completion_tokens or 0,
                    }
                    yield {"usage": usage_data}

        except OpenAIAPIError as e:
            logger.error("OpenAI API error: %s", e)
            raise

    def validate_config(self) -> bool:
        """Validate OpenAI configuration."""
        super().validate_config()
        if not self.api_key:
            raise ValueError("OpenAI API key is not configured")
        return True
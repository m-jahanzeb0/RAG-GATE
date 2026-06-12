"""
Anthropic provider implementation for RAG-Gate.

Uses the official anthropic Python SDK to generate responses.
Supports both streaming and non-streaming modes via a unified generator.
"""

import logging
from typing import Generator, Union

from anthropic import Anthropic
from anthropic import APIError as AnthropicAPIError

from .base import BaseLLMService

logger = logging.getLogger(__name__)


class AnthropicService(BaseLLMService):
    """Anthropic LLM provider service."""

    provider_name = "anthropic"

    def __init__(self, api_key: str, base_url: str | None = None):
        super().__init__(api_key, base_url)
        self.client = Anthropic(api_key=api_key, base_url=base_url)

    def generate_response(
        self,
        model: str,
        messages: list[dict],
        max_tokens: int = 1024,
        temperature: float = 0.7,
    ) -> Generator[Union[str, dict], None, None]:
        """
        Generate a response from Anthropic.

        Separates system messages from the conversation and uses the
        Anthropic Messages API with streaming enabled.
        """
        self.validate_config()

        # Extract system message if present (Anthropic handles system separately)
        system_content = None
        conversation_messages = []
        for msg in messages:
            if msg["role"] == "system":
                system_content = msg["content"]
            else:
                conversation_messages.append({
                    "role": msg["role"],
                    "content": msg["content"],
                })

        try:
            with self.client.messages.stream(
                model=model,
                messages=conversation_messages,
                system=system_content,
                max_tokens=max_tokens,
                temperature=temperature,
            ) as stream:
                for text in stream.text_stream:
                    yield text

                # After streaming completes, get usage from the final message
                final_message = stream.get_final_message()
                usage_data = {
                    "prompt_tokens": final_message.usage.input_tokens or 0,
                    "completion_tokens": final_message.usage.output_tokens or 0,
                }
                yield {"usage": usage_data}

        except AnthropicAPIError as e:
            logger.error("Anthropic API error: %s", e)
            raise

    def validate_config(self) -> bool:
        """Validate Anthropic configuration."""
        super().validate_config()
        if not self.api_key:
            raise ValueError("Anthropic API key is not configured")
        return True
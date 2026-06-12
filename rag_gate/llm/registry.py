"""
Provider registry for RAG-Gate.

Maps provider names to their service classes and resolves which
service instance to use for a given request.

Extend this registry when adding new providers.
"""

import logging

from django.conf import settings

from .base import BaseLLMService
from .openai_service import OpenAIService
from .anthropic_service import AnthropicService
from .openai_compatible_service import OpenAICompatibleService

logger = logging.getLogger(__name__)


class ProviderRegistry:
    """
    Registry that maps provider names to service classes and resolves
    the appropriate service instance for each request.

    To add a new provider:
        1. Create a new service class inheriting from BaseLLMService.
        2. Add it to the PROVIDER_MAP below.
        3. Add its API key to Django settings.
        4. Add the key retrieval logic to _get_api_key().
    """

    PROVIDER_MAP: dict[str, type[BaseLLMService]] = {
        "openai": OpenAIService,
        "anthropic": AnthropicService,
        "openai-compatible": OpenAICompatibleService,
    }

    def get_provider(
        self,
        provider_name: str,
        model: str,
        base_url: str | None = None,
        api_key_override: str | None = None,
    ) -> BaseLLMService:
        """
        Resolve and return an LLM provider service instance.

        Args:
            provider_name: The name of the provider (e.g., "openai", "anthropic").
            model: The model identifier (used for validation).
            base_url: Optional base URL override (for compatible providers).
            api_key_override: Optional API key override (for per-request key swaps).

        Returns:
            An instance of the appropriate BaseLLMService subclass.

        Raises:
            ValueError: If the provider is unknown or misconfigured.
        """
        if provider_name not in self.PROVIDER_MAP:
            raise ValueError(
                f"Unknown provider '{provider_name}'. "
                f"Available providers: {', '.join(self.PROVIDER_MAP.keys())}"
            )

        service_class = self.PROVIDER_MAP[provider_name]

        # Resolve API key
        api_key = api_key_override or self._get_api_key(provider_name)

        # Build the service instance
        try:
            service = service_class(api_key=api_key, base_url=base_url)
            service.validate_config()
            return service
        except ValueError as e:
            logger.error(
                "Provider configuration error for %s: %s",
                provider_name,
                e,
            )
            raise

    def _get_api_key(self, provider_name: str) -> str:
        """
        Retrieve the API key for a given provider from Django settings.

        Override or extend this method to support encrypted DB-stored keys
        (multi-tenant architecture) in the future.
        """
        key_map = {
            "openai": settings.OPENAI_API_KEY,
            "anthropic": settings.ANTHROPIC_API_KEY,
            "openai-compatible": settings.DEFAULT_OPENAI_COMPATIBLE_API_KEY,
        }

        api_key = key_map.get(provider_name, "")
        if not api_key:
            logger.warning(
                "No API key configured for provider '%s'. "
                "Set the appropriate environment variable in your .env file.",
                provider_name,
            )
        return api_key

    def list_providers(self) -> list[str]:
        """Return the list of registered provider names."""
        return list(self.PROVIDER_MAP.keys())
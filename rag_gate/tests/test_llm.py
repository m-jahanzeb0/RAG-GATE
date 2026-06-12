"""
Tests for LLM provider services.

Covers:
  1. BaseLLMService abstract interface
  2. OpenAIService token generation
  3. AnthropicService token generation
  4. OpenAICompatibleService with custom base_url
  5. ProviderRegistry resolution
  6. Error handling and validation
"""

from unittest.mock import MagicMock, patch

import pytest
from django.conf import settings


@pytest.mark.django_db
class TestBaseLLMService:
    """Tests for the base LLM service interface."""

    def test_base_abstract_cannot_instantiate(self):
        """BaseLLMService should be abstract and not instantiable directly."""
        from llm.base import BaseLLMService

        with pytest.raises(TypeError):
            BaseLLMService(api_key="test_key")

    def test_base_validate_config_no_key(self):
        """validate_config should raise ValueError if no API key."""
        from llm.base import BaseLLMService

        # Create a concrete subclass
        class TestService(BaseLLMService):
            provider_name = "test"

            def generate_response(self, *args, **kwargs):
                yield "test"

        service = TestService(api_key="")
        with pytest.raises(ValueError, match="API key is not configured"):
            service.validate_config()

    def test_base_validate_config_valid_key(self):
        """validate_config should return True with a valid API key."""
        from llm.base import BaseLLMService

        class TestService(BaseLLMService):
            provider_name = "test"

            def generate_response(self, *args, **kwargs):
                yield "test"

        service = TestService(api_key="valid_key_123")
        result = service.validate_config()
        assert result is True

    def test_base_build_headers(self):
        """_build_headers should return proper Authorization header."""
        from llm.base import BaseLLMService

        class TestService(BaseLLMService):
            provider_name = "test"

            def generate_response(self, *args, **kwargs):
                yield "test"

        service = TestService(api_key="sk-test-key")
        headers = service._build_headers()
        assert headers["Content-Type"] == "application/json"
        assert headers["Authorization"] == "Bearer sk-test-key"

    def test_base_provider_name_set(self):
        """Concrete services should have provider_name set."""
        from llm.base import BaseLLMService

        class TestService(BaseLLMService):
            provider_name = "my-custom-provider"

            def generate_response(self, *args, **kwargs):
                yield "test"

        service = TestService(api_key="key")
        assert service.provider_name == "my-custom-provider"


class TestOpenAIService:
    """Tests for the OpenAI service."""

    def test_provider_name(self):
        """OpenAIService should have the correct provider name."""
        from llm.openai_service import OpenAIService

        assert OpenAIService.provider_name == "openai"

    @patch("llm.openai_service.OpenAI")
    def test_generate_response_yields_tokens(self, mock_openai, mock_openai_response):
        """OpenAIService should yield tokens from the stream response."""
        from llm.openai_service import OpenAIService

        # Mock the OpenAI client and stream
        mock_client = MagicMock()
        mock_openai.return_value = mock_client
        mock_client.chat.completions.create.return_value = mock_openai_response

        service = OpenAIService(api_key="sk-test")
        tokens = list(service.generate_response(
            model="gpt-4o",
            messages=[{"role": "user", "content": "Hello"}],
        ))

        # Should yield "Hello", " world", and the usage dict
        assert len(tokens) == 3
        assert tokens[0] == "Hello"
        assert tokens[1] == " world"
        assert isinstance(tokens[2], dict)
        assert "usage" in tokens[2]

    @patch("llm.openai_service.OpenAI")
    def test_generate_response_calls_create_with_stream(self, mock_openai):
        """OpenAIService should call create with stream=True."""
        from llm.openai_service import OpenAIService

        mock_client = MagicMock()
        mock_openai.return_value = mock_client
        mock_client.chat.completions.create.return_value = []

        service = OpenAIService(api_key="sk-test")
        list(service.generate_response(
            model="gpt-4o",
            messages=[{"role": "user", "content": "Hi"}],
            max_tokens=512,
            temperature=0.5,
        ))

        mock_client.chat.completions.create.assert_called_once_with(
            model="gpt-4o",
            messages=[{"role": "user", "content": "Hi"}],
            max_tokens=512,
            temperature=0.5,
            stream=True,
            stream_options={"include_usage": True},
        )

    @patch("llm.openai_service.OpenAI")
    def test_validate_config_empty_key_raises(self, mock_openai):
        """OpenAIService should raise on empty API key."""
        from llm.openai_service import OpenAIService

        service = OpenAIService(api_key="")
        with pytest.raises(ValueError, match="API key is not configured"):
            service.validate_config()


class TestAnthropicService:
    """Tests for the Anthropic service."""

    def test_provider_name(self):
        """AnthropicService should have the correct provider name."""
        from llm.anthropic_service import AnthropicService

        assert AnthropicService.provider_name == "anthropic"

    @patch("llm.anthropic_service.Anthropic")
    def test_generate_response_yields_tokens(self, mock_anthropic, mock_anthropic_response):
        """AnthropicService should yield tokens from the stream response."""
        from llm.anthropic_service import AnthropicService

        mock_client = MagicMock()
        mock_anthropic.return_value = mock_client
        mock_client.messages.stream.return_value = mock_anthropic_response

        service = AnthropicService(api_key="sk-ant-test")
        tokens = list(service.generate_response(
            model="claude-3-opus-20240229",
            messages=[{"role": "user", "content": "Hello"}],
        ))

        assert len(tokens) == 3
        assert tokens[0] == "Hello"
        assert tokens[1] == " world"
        assert isinstance(tokens[2], dict)
        assert "usage" in tokens[2]

    @patch("llm.anthropic_service.Anthropic")
    def test_generate_response_with_system_message(self, mock_anthropic, mock_anthropic_response):
        """AnthropicService should separate system messages."""
        from llm.anthropic_service import AnthropicService

        mock_client = MagicMock()
        mock_anthropic.return_value = mock_client
        mock_client.messages.stream.return_value = mock_anthropic_response

        service = AnthropicService(api_key="sk-ant-test")
        list(service.generate_response(
            model="claude-3-sonnet-20240229",
            messages=[
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": "Hello"},
            ],
        ))

        # Should call stream with system parameter
        mock_client.messages.stream.assert_called_once()
        kwargs = mock_client.messages.stream.call_args[1]
        assert kwargs["system"] == "You are a helpful assistant."
        assert kwargs["messages"] == [{"role": "user", "content": "Hello"}]

    @patch("llm.anthropic_service.Anthropic")
    def test_validate_config_empty_key_raises(self, mock_anthropic):
        """AnthropicService should raise on empty API key."""
        from llm.anthropic_service import AnthropicService

        service = AnthropicService(api_key="")
        with pytest.raises(ValueError, match="API key is not configured"):
            service.validate_config()


class TestOpenAICompatibleService:
    """Tests for the OpenAI-compatible service."""

    def test_provider_name(self):
        """OpenAICompatibleService should have the correct provider name."""
        from llm.openai_compatible_service import OpenAICompatibleService

        assert OpenAICompatibleService.provider_name == "openai-compatible"

    def test_init_requires_base_url(self):
        """OpenAICompatibleService should raise without a base_url."""
        from llm.openai_compatible_service import OpenAICompatibleService

        with pytest.raises(ValueError, match="base_url"):
            OpenAICompatibleService(api_key="sk-test")

    @patch("llm.openai_compatible_service.OpenAI")
    def test_generate_response_custom_url(self, mock_openai):
        """OpenAICompatibleService should use the provided base_url."""
        from llm.openai_compatible_service import OpenAICompatibleService

        mock_client = MagicMock()
        mock_openai.return_value = mock_client
        mock_client.chat.completions.create.return_value = []

        service = OpenAICompatibleService(
            api_key="gsk-test",
            base_url="https://api.groq.com/openai/v1",
        )

        list(service.generate_response(
            model="llama3-70b-8192",
            messages=[{"role": "user", "content": "Hi"}],
        ))

        mock_openai.assert_called_once_with(
            api_key="gsk-test",
            base_url="https://api.groq.com/openai/v1",
        )

    @patch("llm.openai_compatible_service.OpenAI")
    def test_validate_config_empty_key_raises(self, mock_openai):
        """OpenAICompatibleService should raise on empty API key or missing base_url."""
        from llm.openai_compatible_service import OpenAICompatibleService

        with pytest.raises(ValueError, match="base_url"):
            OpenAICompatibleService(api_key="sk-test", base_url="")


class TestProviderRegistry:
    """Tests for the provider registry."""

    def test_get_openai_provider(self):
        """Registry should return an OpenAIService instance."""
        from llm.registry import ProviderRegistry

        registry = ProviderRegistry()
        provider = registry.get_provider(provider_name="openai", model="gpt-4o")
        assert provider.provider_name == "openai"

    def test_get_anthropic_provider(self):
        """Registry should return an AnthropicService instance."""
        from llm.registry import ProviderRegistry

        registry = ProviderRegistry()
        provider = registry.get_provider(provider_name="anthropic", model="claude-3")
        assert provider.provider_name == "anthropic"

    def test_unknown_provider_raises(self):
        """Registry should raise for unknown providers."""
        from llm.registry import ProviderRegistry

        registry = ProviderRegistry()
        with pytest.raises(ValueError, match="Unknown provider"):
            registry.get_provider(provider_name="non-existent", model="test")

    def test_list_providers(self):
        """Registry should list all available providers."""
        from llm.registry import ProviderRegistry

        registry = ProviderRegistry()
        providers = registry.list_providers()
        assert "openai" in providers
        assert "anthropic" in providers
        assert "openai-compatible" in providers
        assert len(providers) == 3

    def test_get_provider_with_api_key_override(self):
        """Registry should use the override API key when provided."""
        from llm.registry import ProviderRegistry

        registry = ProviderRegistry()
        provider = registry.get_provider(
            provider_name="openai",
            model="gpt-4o",
            api_key_override="sk-override-key",
        )
        assert provider.api_key == "sk-override-key"


class TestCeleryTasks:
    """Tests for the Celery background tasks."""

    @pytest.mark.django_db
    def test_update_db_quota_creates_record(self, test_user):
        """update_db_quota should create an APIQuota record for the user."""
        from llm.tasks import update_db_quota

        update_db_quota(test_user.pk)

        from gateway.models import APIQuota
        quota = APIQuota.objects.get(user=test_user)
        assert quota.requests_used == 1
        assert quota.daily_limit == 30

    @pytest.mark.django_db
    def test_update_db_quota_increments_existing(self, test_user):
        """update_db_quota should increment an existing quota record."""
        from gateway.models import APIQuota
        from llm.tasks import update_db_quota

        APIQuota.objects.create(user=test_user, requests_used=5)
        update_db_quota(test_user.pk)

        quota = APIQuota.objects.get(user=test_user)
        assert quota.requests_used == 6

    def test_log_request_does_not_raise(self):
        """log_request task should execute without error."""
        from llm.tasks import log_request

        # Should not raise any exceptions
        log_request(user_id=1, provider="openai", model="gpt-4", status="success")
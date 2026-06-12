"""
Comprehensive integration tests for gateway/views.py.

Covers:
  1. Unary success path (OpenAI & Anthropic) — mock SDK calls
  2. Streaming SSE path — verify Server-Sent Events format
  3. Upstream failure handling — 502 Bad Gateway
  4. Authentication rejection — 401/403 for missing/invalid keys
  5. Quota exhaustion — 429 Too Many Requests
  6. Analytics endpoint — data aggregation
  7. Invalid request payloads — 400 Bad Request
  8. Unknown provider — 400 Bad Request
"""

import json
from unittest.mock import MagicMock, patch, PropertyMock

import pytest
from django.conf import settings
from django.utils import timezone
from rest_framework import status

pytestmark = pytest.mark.django_db


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture
def valid_chat_payload():
    """Standard valid chat completion request payload."""
    return {
        "provider": "openai",
        "model": "gpt-4o",
        "messages": [
            {"role": "user", "content": "Hello, world!"}
        ],
        "stream": False,
        "max_tokens": 256,
        "temperature": 0.7,
    }


@pytest.fixture
def streaming_chat_payload(valid_chat_payload):
    """Chat payload with streaming enabled."""
    payload = valid_chat_payload.copy()
    payload["stream"] = True
    return payload


@pytest.fixture
def mock_openai_stream():
    """
    Build a mock OpenAI stream response that yields token chunks.

    Simulates the OpenAI SDK streaming API with delta content and usage.
    """
    class MockDelta:
        def __init__(self, content=""):
            self.content = content
            self.role = "assistant"

    class MockChoice:
        def __init__(self, content=""):
            self.delta = MockDelta(content)
            self.index = 0
            self.finish_reason = None

    class MockUsage:
        prompt_tokens = 12
        completion_tokens = 7

    class MockChunk:
        def __init__(self, content="", is_final=False):
            self.choices = [MockChoice(content)] if content else []
            self.usage = MockUsage() if is_final else None
            self.id = "cmpl-mock-123"

    return [
        MockChunk("Hello"),
        MockChunk(" from"),
        MockChunk(" OpenAI"),
        MockChunk("", is_final=True),
    ]


@pytest.fixture
def mock_anthropic_stream():
    """
    Build a mock Anthropic stream response.
    """
    class MockUsage:
        def __init__(self):
            self.input_tokens = 15
            self.output_tokens = 10

    class MockStream:
        def __init__(self):
            self.text_stream = ["Hello", " from", " Anthropic"]

        def get_final_message(self):
            msg = MagicMock()
            msg.usage = MockUsage()
            return msg

        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

    return MockStream()


# =============================================================================
# Tests: Authentication
# =============================================================================

class TestChatAuth:
    """Tests for authentication on the chat endpoint."""

    def test_chat_unauthenticated(self, api_client, valid_chat_payload):
        """Request without API key should return 401/403."""
        response = api_client.post(
            "/api/v1/chat/",
            data=valid_chat_payload,
            format="json",
        )
        assert response.status_code in (
            status.HTTP_401_UNAUTHORIZED,
            status.HTTP_403_FORBIDDEN,
        )

    def test_chat_invalid_key(self, api_client, valid_chat_payload):
        """Request with invalid API key should return 401/403."""
        api_client.credentials(HTTP_AUTHORIZATION="Api-Key invalid_key")
        response = api_client.post(
            "/api/v1/chat/",
            data=valid_chat_payload,
            format="json",
        )
        assert response.status_code in (
            status.HTTP_401_UNAUTHORIZED,
            status.HTTP_403_FORBIDDEN,
        )


# =============================================================================
# Tests: Unary Success Paths
# =============================================================================

class TestUnaryOpenAI:
    """Unary (non-streaming) OpenAI completion via POST /api/v1/chat/."""

    @patch("llm.openai_service.OpenAI")
    def test_unary_openai_success(
        self, mock_openai, authenticated_client, valid_chat_payload, mock_redis,
        mock_openai_stream,
    ):
        """Successful OpenAI unary call should return 200 with content."""
        mock_client = MagicMock()
        mock_openai.return_value = mock_client
        mock_client.chat.completions.create.return_value = mock_openai_stream

        response = authenticated_client.post(
            "/api/v1/chat/",
            data=valid_chat_payload,
            format="json",
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        assert data["model"] == "gpt-4o"
        assert data["provider"] == "openai"
        assert data["content"] == "Hello from OpenAI"
        assert "quota_remaining" in data
        assert "usage" in data
        assert data["usage"]["prompt_tokens"] == 12
        assert data["usage"]["completion_tokens"] == 7

    @patch("llm.openai_service.OpenAI")
    def test_unary_openai_quota_decremented(
        self, mock_openai, authenticated_client, valid_chat_payload, mock_redis,
        mock_openai_stream,
    ):
        """After a successful call, quota_remaining should be decremented."""
        mock_client = MagicMock()
        mock_openai.return_value = mock_client
        mock_client.chat.completions.create.return_value = mock_openai_stream

        # First request (INCR returns 1, so remaining = 30 - 1 = 29, then decremented by 1 = 28)
        mock_redis.incr.return_value = 1
        response = authenticated_client.post(
            "/api/v1/chat/",
            data=valid_chat_payload,
            format="json",
        )
        assert response.status_code == status.HTTP_200_OK
        assert response.json()["quota_remaining"] == 28


class TestUnaryAnthropic:
    """Unary (non-streaming) Anthropic completion via POST /api/v1/chat/."""

    @patch("llm.anthropic_service.Anthropic")
    def test_unary_anthropic_success(
        self, mock_anthropic, authenticated_client, mock_redis,
        mock_anthropic_stream,
    ):
        """Successful Anthropic unary call should return 200 with content."""
        mock_client = MagicMock()
        mock_anthropic.return_value = mock_client
        mock_client.messages.stream.return_value = mock_anthropic_stream

        payload = {
            "provider": "anthropic",
            "model": "claude-3-opus-20240229",
            "messages": [{"role": "user", "content": "Hi"}],
            "stream": False,
            "max_tokens": 256,
            "temperature": 0.7,
        }

        response = authenticated_client.post(
            "/api/v1/chat/",
            data=payload,
            format="json",
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["model"] == "claude-3-opus-20240229"
        assert data["provider"] == "anthropic"
        assert data["content"] == "Hello from Anthropic"
        assert "usage" in data
        assert data["usage"]["prompt_tokens"] == 15
        assert data["usage"]["completion_tokens"] == 10

    @patch("llm.anthropic_service.Anthropic")
    def test_unary_anthropic_quota_decremented(
        self, mock_anthropic, authenticated_client, mock_redis,
        mock_anthropic_stream,
    ):
        """Anthropic call should decrement quota in response."""
        mock_client = MagicMock()
        mock_anthropic.return_value = mock_client
        mock_client.messages.stream.return_value = mock_anthropic_stream

        mock_redis.incr.return_value = 5

        payload = {
            "provider": "anthropic",
            "model": "claude-3-sonnet",
            "messages": [{"role": "user", "content": "Hi"}],
            "stream": False,
        }

        response = authenticated_client.post(
            "/api/v1/chat/",
            data=payload,
            format="json",
        )
        assert response.status_code == status.HTTP_200_OK
        assert response.json()["quota_remaining"] == 24  # 30 - 5 - 1


# =============================================================================
# Tests: Streaming SSE Path
# =============================================================================

class TestStreaming:
    """Streaming (SSE) completion via POST /api/v1/chat/ with stream=true."""

    @patch("llm.openai_service.OpenAI")
    def test_streaming_sse_format(
        self, mock_openai, authenticated_client, streaming_chat_payload,
        mock_redis, mock_openai_stream,
    ):
        """Streaming response should yield SSE-formatted events."""
        mock_client = MagicMock()
        mock_openai.return_value = mock_client
        mock_client.chat.completions.create.return_value = mock_openai_stream

        response = authenticated_client.post(
            "/api/v1/chat/",
            data=streaming_chat_payload,
            format="json",
        )

        assert response.status_code == status.HTTP_200_OK
        assert response["Content-Type"] == "text/event-stream"
        assert response["Cache-Control"] == "no-cache"

        # Read the streaming content
        chunks = list(response.streaming_content)
        sse_events = [chunk.decode("utf-8") for chunk in chunks]

        # Should have 3 token events + 1 done event
        assert len(sse_events) == 4

        # Verify SSE format
        for event in sse_events:
            assert event.startswith("data: ")
            assert event.endswith("\n\n")

        # Verify token content
        token_events = [json.loads(e.replace("data: ", "").strip()) for e in sse_events]
        assert token_events[0]["event"] == "token"
        assert token_events[0]["token"] == "Hello"
        assert token_events[1]["token"] == " from"
        assert token_events[2]["token"] == " OpenAI"

        # Verify done event
        assert token_events[3]["event"] == "done"
        assert "usage" in token_events[3]
        assert "quota_remaining" in token_events[3]

    @patch("llm.openai_service.OpenAI")
    def test_streaming_system_message(
        self, mock_openai, authenticated_client, mock_redis,
        mock_openai_stream,
    ):
        """Streaming with a system message should work correctly."""
        mock_client = MagicMock()
        mock_openai.return_value = mock_client
        mock_client.chat.completions.create.return_value = mock_openai_stream

        payload = {
            "provider": "openai",
            "model": "gpt-4o",
            "messages": [
                {"role": "system", "content": "You are a poet."},
                {"role": "user", "content": "Write a haiku"},
            ],
            "stream": True,
        }

        response = authenticated_client.post(
            "/api/v1/chat/",
            data=payload,
            format="json",
        )

        assert response.status_code == status.HTTP_200_OK

        chunks = list(response.streaming_content)
        sse_events = [chunk.decode("utf-8") for chunk in chunks]

        # Verify system message was passed to the SDK
        call_kwargs = mock_client.chat.completions.create.call_args[1]
        assert call_kwargs["messages"][0]["role"] == "system"
        assert call_kwargs["messages"][1]["role"] == "user"

        # Verify token content still correct
        token_events = [
            json.loads(e.replace("data: ", "").strip())
            for e in sse_events if '"token"' in e
        ]
        assert len(token_events) >= 2


# =============================================================================
# Tests: Error Handling
# =============================================================================

class TestErrorHandling:
    """Tests for error handling — 400, 502, 429 responses."""

    def test_missing_provider(self, authenticated_client, mock_redis):
        """Missing provider should return 400."""
        payload = {
            "model": "gpt-4o",
            "messages": [{"role": "user", "content": "Hi"}],
        }
        response = authenticated_client.post(
            "/api/v1/chat/",
            data=payload,
            format="json",
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_missing_messages(self, authenticated_client, mock_redis):
        """Missing messages should return 400."""
        payload = {
            "provider": "openai",
            "model": "gpt-4o",
        }
        response = authenticated_client.post(
            "/api/v1/chat/",
            data=payload,
            format="json",
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_invalid_message_role(self, authenticated_client, mock_redis):
        """Invalid message role should return 400."""
        payload = {
            "provider": "openai",
            "model": "gpt-4o",
            "messages": [{"role": "invalid_role", "content": "Hi"}],
        }
        response = authenticated_client.post(
            "/api/v1/chat/",
            data=payload,
            format="json",
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_unknown_provider(self, authenticated_client, mock_redis):
        """Unknown provider should return 400."""
        payload = {
            "provider": "nonexistent-provider",
            "model": "gpt-4o",
            "messages": [{"role": "user", "content": "Hi"}],
        }
        response = authenticated_client.post(
            "/api/v1/chat/",
            data=payload,
            format="json",
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        # DRF serializer returns field-level errors
        data = response.json()
        assert "provider" in data

    @patch("llm.openai_service.OpenAI")
    def test_upstream_openai_error(
        self, mock_openai, authenticated_client, valid_chat_payload,
        mock_redis,
    ):
        """OpenAI upstream error should return 502 Bad Gateway."""
        mock_client = MagicMock()
        mock_openai.return_value = mock_client
        from openai import APIError as OpenAIAPIError
        mock_client.chat.completions.create.side_effect = OpenAIAPIError(
            message="Upstream server error",
            request=MagicMock(),
            body={"error": "server_error"},
        )

        response = authenticated_client.post(
            "/api/v1/chat/",
            data=valid_chat_payload,
            format="json",
        )

        assert response.status_code == status.HTTP_502_BAD_GATEWAY
        data = response.json()
        assert "Provider error" in data["error"]

    @patch("llm.anthropic_service.Anthropic")
    def test_upstream_anthropic_error(
        self, mock_anthropic, authenticated_client, mock_redis,
    ):
        """Anthropic upstream error should return 502 Bad Gateway."""
        mock_client = MagicMock()
        mock_anthropic.return_value = mock_client
        from anthropic import APIError as AnthropicAPIError
        mock_client.messages.stream.side_effect = AnthropicAPIError(
            message="Anthropic unavailable",
            request=MagicMock(),
            body={"error": "overloaded"},
        )

        payload = {
            "provider": "anthropic",
            "model": "claude-3-opus",
            "messages": [{"role": "user", "content": "Hi"}],
            "stream": False,
        }

        response = authenticated_client.post(
            "/api/v1/chat/",
            data=payload,
            format="json",
        )

        assert response.status_code == status.HTTP_502_BAD_GATEWAY
        data = response.json()
        assert "Provider error" in data["error"]

    def test_quota_exhausted_returns_429(self, mock_redis, authenticated_client, valid_chat_payload):
        """When Redis returns >30 INCR, the endpoint should return 429."""
        # Simulate quota exhausted — INCR returns 31 (daily limit + 1)
        mock_redis.incr.return_value = 31

        response = authenticated_client.post(
            "/api/v1/chat/",
            data=valid_chat_payload,
            format="json",
        )

        assert response.status_code == status.HTTP_429_TOO_MANY_REQUESTS
        data = response.json()
        assert "Daily quota exceeded" in str(data.get("error", "")) or "exceeded" in str(data.get("detail", ""))

    def test_quota_exhausted_no_llm_call(self, mock_redis, authenticated_client, valid_chat_payload, mocker):
        """When quota is exhausted, no LLM provider should be called."""
        mock_redis.incr.return_value = 31

        # Spy on get_provider to verify it's never called when quota is exhausted
        from gateway.views import provider_registry
        registry_spy = mocker.spy(provider_registry, "get_provider")

        response = authenticated_client.post(
            "/api/v1/chat/",
            data=valid_chat_payload,
            format="json",
        )

        assert response.status_code == status.HTTP_429_TOO_MANY_REQUESTS
        # Provider should NOT have been resolved (quota check happens first)
        registry_spy.assert_not_called()
        data = response.json()
        assert "error" in data or "detail" in data

    def test_quota_exhausted_streaming(self, mock_redis, authenticated_client, streaming_chat_payload):
        """Quota exhaustion should return 429 even for streaming requests."""
        mock_redis.incr.return_value = 31

        response = authenticated_client.post(
            "/api/v1/chat/",
            data=streaming_chat_payload,
            format="json",
        )

        assert response.status_code == status.HTTP_429_TOO_MANY_REQUESTS


# =============================================================================
# Tests: OpenAI-Compatible Provider
# =============================================================================

class TestOpenAICompatible:
    """Tests for the OpenAI-compatible provider path."""

    @patch("llm.openai_compatible_service.OpenAI")
    def test_openai_compatible_with_base_url(
        self, mock_openai, authenticated_client, mock_redis,
    ):
        """OpenAI-compatible provider with custom base_url should work."""
        mock_client = MagicMock()
        mock_openai.return_value = mock_client

        class MockDelta:
            def __init__(self, content=""):
                self.content = content
                self.role = "assistant"

        class MockChoice:
            def __init__(self, content=""):
                self.delta = MockDelta(content)
                self.index = 0

        class MockUsage:
            prompt_tokens = 5
            completion_tokens = 3

        class MockChunk:
            def __init__(self, content="", is_final=False):
                self.choices = [MockChoice(content)] if content else []
                self.usage = MockUsage() if is_final else None
                self.id = "cmpl-mock"

        mock_client.chat.completions.create.return_value = [
            MockChunk("Hello from Groq"),
            MockChunk("", is_final=True),
        ]

        payload = {
            "provider": "openai-compatible",
            "model": "llama3-70b-8192",
            "messages": [{"role": "user", "content": "Hi"}],
            "stream": False,
            "base_url": "https://api.groq.com/openai/v1",
        }

        response = authenticated_client.post(
            "/api/v1/chat/",
            data=payload,
            format="json",
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["provider"] == "openai-compatible"
        assert data["content"] == "Hello from Groq"
        assert data["model"] == "llama3-70b-8192"


# =============================================================================
# Tests: Analytics Endpoint
# =============================================================================

class TestAnalytics:
    """Tests for the GET /api/v1/analytics/ endpoint."""

    def test_analytics_unauthenticated(self, api_client):
        """Analytics endpoint should require authentication."""
        response = api_client.get("/api/v1/analytics/")
        assert response.status_code in (
            status.HTTP_401_UNAUTHORIZED,
            status.HTTP_403_FORBIDDEN,
        )

    def test_analytics_empty(
        self, authenticated_client, mock_redis, test_user,
    ):
        """Analytics should return zero counts when no requests exist."""
        response = authenticated_client.get("/api/v1/analytics/")
        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        assert data["total_requests_30_days"] == 0
        assert data["current_day_usage"] == 0
        assert data["quota_limit"] == 30
        assert data["provider_distribution"] == {}
        assert data["usage_history_7_days"] == []

    def test_analytics_with_data(
        self, authenticated_client, mock_redis, test_user,
    ):
        """Analytics should return aggregated counts from RequestLog records."""
        from gateway.models import RequestLog

        now = timezone.now()
        yesterday = now - timezone.timedelta(days=1)
        two_days_ago = now - timezone.timedelta(days=2)

        # Create some historical data
        RequestLog.objects.create(
            user=test_user, provider="openai", model="gpt-4o",
            status="success", created_at=now,
        )
        RequestLog.objects.create(
            user=test_user, provider="openai", model="gpt-4o",
            status="success", created_at=now,
        )
        RequestLog.objects.create(
            user=test_user, provider="anthropic", model="claude-3",
            status="success", created_at=yesterday,
        )
        RequestLog.objects.create(
            user=test_user, provider="openai-compatible",
            model="llama3", status="error", created_at=two_days_ago,
        )

        response = authenticated_client.get("/api/v1/analytics/")
        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        assert data["total_requests_30_days"] == 4
        assert data["current_day_usage"] == 2  # 2 today
        assert data["quota_limit"] == 30
        assert data["provider_distribution"]["openai"] == 2
        assert data["provider_distribution"]["anthropic"] == 1
        assert data["provider_distribution"]["openai-compatible"] == 1
        assert len(data["usage_history_7_days"]) >= 2  # at least 2 unique days

    def test_analytics_only_user_own_data(
        self, authenticated_client, mock_redis, test_user, db,
    ):
        """Analytics should only show data for the authenticated user."""
        from django.contrib.auth import get_user_model
        from gateway.models import RequestLog

        User = get_user_model()
        other_user = User.objects.create_user(username="other", password="pass")

        # Create data for both users
        RequestLog.objects.create(
            user=other_user, provider="openai", model="gpt-4o",
            status="success",
        )
        RequestLog.objects.create(
            user=test_user, provider="anthropic", model="claude-3",
            status="success",
        )

        response = authenticated_client.get("/api/v1/analytics/")
        data = response.json()

        # Should only see test_user's data
        assert data["total_requests_30_days"] == 1
        assert "anthropic" in data["provider_distribution"]
        assert "openai" not in data["provider_distribution"]
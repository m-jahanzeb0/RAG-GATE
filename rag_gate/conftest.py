"""
Pytest configuration and fixtures for RAG-Gate.

Provides fixtures for:
  - Django test client with API key authentication
  - Mock Redis for quota tests
  - Test users and API keys
  - Mock LLM provider responses
"""

from unittest.mock import MagicMock

import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
import uuid


@pytest.fixture
def api_client():
    """Return an unauthenticated DRF API test client."""
    return APIClient()


@pytest.fixture
def test_user(db):
    """Create and return a test Django user."""
    User = get_user_model()
    user = User.objects.create_user(
        username="testuser",
        password="testpass123",
        email="test@example.com",
    )
    return user


@pytest.fixture
def test_api_key(db, test_user):
    """Create and return a test API key for the test user."""
    from gateway.models import APIKey

    api_key = APIKey.objects.create(
        user=test_user,
        key=f"rg_test_{uuid.uuid4().hex[:32]}",
        name="Test Key",
        is_active=True,
    )
    return api_key


@pytest.fixture
def authenticated_client(api_client, test_api_key):
    """Return an authenticated DRF API client."""
    api_client.credentials(HTTP_AUTHORIZATION=f"Api-Key {test_api_key.key}")
    return api_client


@pytest.fixture
def mock_redis(monkeypatch):
    """
    Mock Redis to avoid requiring a running Redis instance during tests.

    Returns a MagicMock that simulates Redis INCR/GET/EXPIRE behavior.
    """
    from gateway.throttling import RedisQuotaThrottle

    mock_client = MagicMock()

    # Default INCR returns 1 (first request), so quota is always available
    mock_client.incr.return_value = 1
    mock_client.get.return_value = "0"
    mock_client.expire.return_value = True

    # Patch the Redis client creation in the throttle
    def mock_get_redis(self):
        return mock_client

    monkeypatch.setattr(RedisQuotaThrottle, "_get_redis", mock_get_redis)

    return mock_client


@pytest.fixture
def quota_throttle(mock_redis):
    """Return a RedisQuotaThrottle instance with mocked Redis."""
    from gateway.throttling import RedisQuotaThrottle

    throttle = RedisQuotaThrottle()
    throttle.redis_client = mock_redis
    return throttle


@pytest.fixture
def mock_openai_response():
    """
    Mock an OpenAI streaming response.

    Returns a list of mock chunk objects that simulate the OpenAI API response format.
    """
    class MockDelta:
        def __init__(self, content):
            self.content = content
            self.role = "assistant"

    class MockChoice:
        def __init__(self, content):
            self.delta = MockDelta(content)
            self.index = 0
            self.finish_reason = None

    class MockUsage:
        def __init__(self):
            self.prompt_tokens = 10
            self.completion_tokens = 5

    class MockChunk:
        def __init__(self, content, is_final=False):
            self.choices = [MockChoice(content)] if content else []
            self.usage = MockUsage() if is_final else None
            self.id = "cmpl-test"

    return [
        MockChunk("Hello"),
        MockChunk(" world"),
        MockChunk("", is_final=True),
    ]


@pytest.fixture
def mock_anthropic_response():
    """
    Mock an Anthropic streaming response.

    Mocks the anthropic stream API generator.
    """
    class MockUsage:
        def __init__(self):
            self.input_tokens = 10
            self.output_tokens = 5

    class MockStream:
        def __init__(self):
            self.text_stream = ["Hello", " world"]

        def get_final_message(self):
            msg = MagicMock()
            msg.usage = MockUsage()
            return msg

        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

    return MockStream()
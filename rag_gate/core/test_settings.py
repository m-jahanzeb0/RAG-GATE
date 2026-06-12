"""
Test settings for RAG-Gate.

Overrides the main settings to use SQLite in-memory database for tests,
since PostgreSQL may not be available in CI/local development without Docker.
"""

from .settings import *  # noqa: F403

# Use SQLite for tests
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": ":memory:",
    }
}

# Disable Celery task execution during tests — tasks run synchronously
CELERY_TASK_ALWAYS_EAGER = True
CELERY_TASK_EAGER_PROPAGATES = True

# Use a simpler secret key for tests
SECRET_KEY = "test-secret-key-not-for-production"

# Provide test API keys so registry/provider validation passes
OPENAI_API_KEY = "sk-test-openai-key"
ANTHROPIC_API_KEY = "sk-ant-test-anthropic-key"
DEFAULT_OPENAI_COMPATIBLE_API_KEY = "gsk-test-compatible-key"
DEFAULT_OPENAI_COMPATIBLE_BASE_URL = "https://api.groq.com/openai/v1"
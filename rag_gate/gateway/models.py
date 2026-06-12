"""
API Quota tracking model, API Key model, and Request Log for RAG-Gate.

- APIKey: Stores static API keys for machine-to-machine authentication.
- APIQuota: Tracks daily request usage per user with automatic reset detection.
- RequestLog: Persistent log of LLM API requests for analytics.
"""

import uuid
from django.db import models
from django.conf import settings
from django.utils import timezone


class APIKey(models.Model):
    """Static API key for machine-to-machine authentication."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="api_keys",
    )
    key = models.CharField(max_length=128, unique=True, db_index=True)
    name = models.CharField(max_length=128, help_text="A label to identify this key.")
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "API Key"
        verbose_name_plural = "API Keys"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.name} ({self.key[:8]}...)"


class APIQuota(models.Model):
    """
    Tracks daily API usage per user.

    The primary enforcement happens via Redis atomic counters for speed
    and race-condition safety. This model serves as the persistent record
    and source of truth for historical usage and quota reset logging.

    On each request, if the date has changed since last_reset, the usage
    counters are automatically reset.
    """

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="api_quota",
    )
    daily_limit = models.PositiveIntegerField(default=30)
    requests_used = models.PositiveIntegerField(default=0)
    last_reset = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "API Quota"
        verbose_name_plural = "API Quotas"

    def __str__(self):
        return f"{self.user} - {self.requests_used}/{self.daily_limit}"

    def reset_if_needed(self):
        """
        Reset the usage counter if a new day has started.
        Called before any quota check to ensure the daily limit is fresh.
        """
        now = timezone.now()
        if self.last_reset.date() < now.date():
            self.requests_used = 0
            self.last_reset = now
            self.save(update_fields=["requests_used", "last_reset"])
            return True
        return False

    def increment_usage(self):
        """Atomically increment the usage counter (called after LLM response)."""
        if self.reset_if_needed():
            # Reset was performed — DB was already updated by reset_if_needed
            # Now increment from 0 to 1
            APIQuota.objects.filter(pk=self.pk).update(
                requests_used=models.F("requests_used") + 1,
                updated_at=timezone.now(),
            )
        else:
            APIQuota.objects.filter(pk=self.pk).update(
                requests_used=models.F("requests_used") + 1,
                updated_at=timezone.now(),
            )
        self.refresh_from_db(fields=["requests_used", "updated_at"])

    @property
    def remaining(self):
        """Return remaining requests for today."""
        return max(0, self.daily_limit - self.requests_used)

    @property
    def is_exhausted(self):
        """Check if the daily quota has been consumed."""
        return self.requests_used >= self.daily_limit


class RequestLog(models.Model):
    """
    Persistent log of LLM API requests for analytics and dashboard metrics.

    Populated asynchronously by the Celery `log_request` task after each
    LLM API call completes. Used by the /api/v1/analytics/ endpoint.
    """

    id = models.BigAutoField(primary_key=True)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="request_logs",
    )
    provider = models.CharField(
        max_length=64,
        db_index=True,
        help_text="LLM provider name (openai, anthropic, openai-compatible)",
    )
    model = models.CharField(
        max_length=256,
        help_text="Model identifier (e.g., gpt-4o, claude-3-opus)",
    )
    status = models.CharField(
        max_length=16,
        db_index=True,
        choices=[("success", "Success"), ("error", "Error")],
        help_text="Request outcome",
    )
    created_at = models.DateTimeField(
        default=timezone.now,
        db_index=True,
        help_text="When the request was made",
    )

    class Meta:
        verbose_name = "Request Log"
        verbose_name_plural = "Request Logs"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["user", "created_at"]),
            models.Index(fields=["user", "provider"]),
        ]

    def __str__(self):
        return f"{self.user} - {self.provider}/{self.model} - {self.status} @ {self.created_at:%Y-%m-%d}"
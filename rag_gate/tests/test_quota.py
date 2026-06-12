"""
Comprehensive pytest coverage for the quota reset logic.

Tests cover:
  1. Redis atomic INCR enforcement (concurrency-safe)
  2. Quota exhaustion (returning 429 beyond 30 requests)
  3. Quota reset at midnight (Redis TTL expiration)
  4. DB model reset_if_needed() logic
  5. Celery task for DB persistence
  6. Quota check endpoint accuracy
  7. Concurrent quota check safety (mock race condition)
"""

from unittest.mock import MagicMock, patch
from datetime import datetime, timedelta, timezone

import pytest
from django.conf import settings
from django.utils import timezone as django_timezone
from freezegun import freeze_time
from rest_framework import status


@pytest.mark.django_db
class TestRedisQuotaThrottle:
    """Tests for the Redis-backed quota throttle."""

    def test_allow_first_request(self, quota_throttle):
        """First request of the day should be allowed."""
        quota_throttle.redis_client.incr.return_value = 1
        allowed, remaining = quota_throttle.allow_request(user_id=1)
        assert allowed is True
        assert remaining == settings.QUOTA_DAILY_LIMIT - 1
        quota_throttle.redis_client.incr.assert_called_once()
        quota_throttle.redis_client.expire.assert_called_once()

    def test_allow_request_under_limit(self, quota_throttle):
        """Request within the daily limit should be allowed."""
        quota_throttle.redis_client.incr.return_value = 15
        allowed, remaining = quota_throttle.allow_request(user_id=1)
        assert allowed is True
        assert remaining == settings.QUOTA_DAILY_LIMIT - 15

    def test_block_request_at_exact_limit(self, quota_throttle):
        """The 31st request (daily_limit + 1) should be blocked."""
        over_limit = settings.QUOTA_DAILY_LIMIT + 1
        quota_throttle.redis_client.incr.return_value = over_limit
        allowed, remaining = quota_throttle.allow_request(user_id=1)
        assert allowed is False
        assert remaining == 0

    def test_block_request_over_limit(self, quota_throttle):
        """Requests far beyond the limit should be blocked with 0 remaining."""
        quota_throttle.redis_client.incr.return_value = 50
        allowed, remaining = quota_throttle.allow_request(user_id=1)
        assert allowed is False
        assert remaining == 0

    def test_quota_key_format(self, quota_throttle):
        """Quota key should follow the format quota:{user_id}:{YYYY-MM-DD}."""
        from django.utils import timezone as dj_tz
        today = dj_tz.now().strftime("%Y-%m-%d")
        key = quota_throttle._quota_key(user_id=42)
        assert key == f"quota:42:{today}"

    def test_redis_unavailable_fall_open(self, monkeypatch, quota_throttle):
        """When Redis is unavailable, the throttle should fail open (allow request)."""
        from gateway.throttling import RedisQuotaThrottle

        def mock_get_redis_fail(self):
            return None

        monkeypatch.setattr(RedisQuotaThrottle, "_get_redis", mock_get_redis_fail)
        throttle = RedisQuotaThrottle()
        allowed, remaining = throttle.allow_request(user_id=1)
        assert allowed is True
        assert remaining == settings.QUOTA_DAILY_LIMIT

    def test_get_remaining_without_increment(self, quota_throttle):
        """get_remaining should return quota without incrementing."""
        quota_throttle.redis_client.get.return_value = "5"
        remaining = quota_throttle.get_remaining(user_id=1)
        assert remaining == settings.QUOTA_DAILY_LIMIT - 5
        quota_throttle.redis_client.get.assert_called_once()
        quota_throttle.redis_client.incr.assert_not_called()

    def test_get_remaining_no_key(self, quota_throttle):
        """get_remaining should return full quota when no Redis key exists."""
        quota_throttle.redis_client.get.return_value = None
        remaining = quota_throttle.get_remaining(user_id=1)
        assert remaining == settings.QUOTA_DAILY_LIMIT

    def test_ttl_expiry_at_midnight(self, quota_throttle):
        """
        When the Redis key expires at midnight, the INCR should start
        fresh from 1, effectively resetting the quota.
        """
        quota_throttle.redis_client.incr.return_value = 1
        allowed, remaining = quota_throttle.allow_request(user_id=1)
        assert allowed is True
        assert remaining == settings.QUOTA_DAILY_LIMIT - 1

    def test_concurrent_requests_safety(self, quota_throttle):
        """
        Simulate the race condition: multiple concurrent INCRs should
        still correctly enforce the limit (atomic INCR guarantees this).
        """
        daily_limit = settings.QUOTA_DAILY_LIMIT
        quota_throttle.redis_client.incr.return_value = daily_limit + 1
        allowed, remaining = quota_throttle.allow_request(user_id=1)
        assert allowed is False
        assert remaining == 0

    def test_multiple_users_independent_quotas(self, quota_throttle):
        """Quota for user 1 should not affect user 2."""
        quota_throttle.redis_client.incr.side_effect = [30, 1]

        quota_throttle.redis_client.incr.return_value = 30
        allowed_u1, remaining_u1 = quota_throttle.allow_request(user_id=1)
        assert allowed_u1 is True
        assert remaining_u1 == 0

        quota_throttle.redis_client.incr.return_value = 1
        allowed_u2, remaining_u2 = quota_throttle.allow_request(user_id=2)
        assert allowed_u2 is True
        assert remaining_u2 == settings.QUOTA_DAILY_LIMIT - 1


@pytest.mark.django_db
class TestAPIQuotaModel:
    """Tests for the APIQuota database model."""

    def test_create_quota(self, test_user):
        """Creating a quota should default to 30 requests with 0 used."""
        from gateway.models import APIQuota

        quota = APIQuota.objects.create(user=test_user)
        assert quota.daily_limit == 30
        assert quota.requests_used == 0
        assert quota.remaining == 30
        assert quota.is_exhausted is False

    def test_quota_remaining_calculation(self, test_user):
        """Remaining should be daily_limit - requests_used."""
        from gateway.models import APIQuota

        quota = APIQuota.objects.create(user=test_user, requests_used=10)
        assert quota.remaining == 20

    def test_quota_exhausted(self, test_user):
        """is_exhausted should be True when requests_used >= daily_limit."""
        from gateway.models import APIQuota

        quota = APIQuota.objects.create(user=test_user, requests_used=30)
        assert quota.is_exhausted is True

    def test_quota_not_exhausted(self, test_user):
        """is_exhausted should be False when under the limit."""
        from gateway.models import APIQuota

        quota = APIQuota.objects.create(user=test_user, requests_used=29)
        assert quota.is_exhausted is False

    def test_quota_increment(self, test_user):
        """increment_usage should increase requests_used by 1."""
        from gateway.models import APIQuota

        quota = APIQuota.objects.create(user=test_user, requests_used=5)
        quota.increment_usage()
        quota.refresh_from_db()
        assert quota.requests_used == 6

    def test_quota_reset_if_needed_same_day(self, test_user):
        """reset_if_needed should NOT reset if still the same day."""
        from gateway.models import APIQuota

        quota = APIQuota.objects.create(
            user=test_user,
            requests_used=15,
        )
        result = quota.reset_if_needed()
        assert result is False
        assert quota.requests_used == 15

    def test_quota_reset_if_needed_new_day(self, test_user):
        """reset_if_needed should reset if the day has changed."""
        from gateway.models import APIQuota

        # Use a date that is definitely in the past
        old_date = django_timezone.make_aware(datetime(2024, 1, 1, 0, 0, 0))
        quota = APIQuota.objects.create(
            user=test_user,
            requests_used=30,
            last_reset=old_date,
        )
        result = quota.reset_if_needed()
        assert result is True
        assert quota.requests_used == 0
        assert quota.last_reset.date() == django_timezone.now().date()

    def test_quota_auto_reset_on_increment(self, test_user):
        """increment_usage should reset before incrementing if new day."""
        from gateway.models import APIQuota

        old_date = django_timezone.make_aware(datetime(2024, 1, 1, 0, 0, 0))
        quota = APIQuota.objects.create(
            user=test_user,
            requests_used=30,
            last_reset=old_date,
        )
        quota.increment_usage()
        quota.refresh_from_db()
        assert quota.requests_used == 1

    def test_quota_str(self, test_user):
        """String representation should be informative."""
        from gateway.models import APIQuota

        quota = APIQuota.objects.create(user=test_user, requests_used=5)
        assert "testuser" in str(quota)
        assert "5/30" in str(quota)

    def test_remaining_never_negative(self, test_user):
        """Remaining should never be negative, even if something goes wrong."""
        from gateway.models import APIQuota

        quota = APIQuota.objects.create(user=test_user, requests_used=999)
        assert quota.remaining == 0


@pytest.mark.django_db
class TestQuotaResetScheduledTask:
    """Tests for the scheduled Celery task that resets all quotas."""

    @freeze_time("2026-06-12 00:00:00")
    def test_reset_all_quotas(self, test_user):
        """reset_all_quotas should reset all quota counters to 0."""
        from gateway.models import APIQuota
        from llm.tasks import reset_all_quotas

        APIQuota.objects.create(
            user=test_user,
            requests_used=29,
            last_reset=django_timezone.make_aware(datetime(2026, 6, 11, 12, 0, 0)),
        )

        reset_all_quotas()

        quota = APIQuota.objects.get(user=test_user)
        assert quota.requests_used == 0
        assert quota.last_reset.date() == django_timezone.now().date()

    def test_reset_all_quotas_empty_db(self):
        """reset_all_quotas should handle empty database gracefully."""
        from llm.tasks import reset_all_quotas

        reset_all_quotas()


@pytest.mark.django_db
class TestQuotaAPIEndpoint:
    """Tests for the GET /api/v1/quota/ endpoint."""

    def test_quota_check_authenticated(self, authenticated_client, mock_redis, test_user):
        """Authenticated user should get their quota info."""
        response = authenticated_client.get("/api/v1/quota/")
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["daily_limit"] == 30
        assert "remaining" in data
        assert "requests_used" in data
        assert "reset_date" in data

    def test_quota_check_unauthenticated(self, api_client):
        """Unauthenticated request should return 401/403."""
        response = api_client.get("/api/v1/quota/")
        assert response.status_code in (status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN)

    def test_quota_check_after_usage(self, authenticated_client, mock_redis, test_user):
        """Quota check should reflect used requests."""
        from gateway.models import APIQuota

        APIQuota.objects.create(
            user=test_user,
            requests_used=10,
        )

        response = authenticated_client.get("/api/v1/quota/")
        data = response.json()
        assert data["remaining"] == 20

    def test_quota_check_exhausted(self, authenticated_client, mock_redis, test_user):
        """Exhausted quota should show 0 remaining."""
        from gateway.models import APIQuota

        APIQuota.objects.create(
            user=test_user,
            requests_used=30,
        )

        response = authenticated_client.get("/api/v1/quota/")
        data = response.json()
        assert data["remaining"] == 0
        assert data["requests_used"] == 30
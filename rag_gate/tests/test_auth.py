"""
Tests for API Key authentication.

Covers:
  1. Valid API key authentication
  2. Missing Authorization header
  3. Invalid API key
  4. Inactive API key
  5. Malformed Authorization header
  6. Incorrect auth keyword
  7. API key creation and management
"""

import pytest
from rest_framework import status
from rest_framework.test import APIClient


@pytest.mark.django_db
class TestAPIKeyAuthentication:
    """Tests for the API key authentication mechanism."""

    def test_authenticate_valid_key(self, authenticated_client):
        """Request with valid API key should succeed."""
        response = authenticated_client.get("/api/v1/quota/")
        assert response.status_code == status.HTTP_200_OK

    def test_authenticate_missing_header(self, api_client):
        """Request without Authorization header should return 401."""
        response = api_client.get("/api/v1/quota/")
        # DRF returns 403 Forbidden when UNAUTHENTICATED_USER=None and auth fails
        assert response.status_code in (status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN)

    def test_authenticate_invalid_key(self, api_client, test_api_key):
        """Request with a random/invalid key should return 401."""
        api_client.credentials(HTTP_AUTHORIZATION="Api-Key invalid_key_12345")
        response = api_client.get("/api/v1/quota/")
        assert response.status_code in (status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN)

    def test_authenticate_inactive_key(self, api_client, test_api_key):
        """Request with an inactive API key should return 401."""
        test_api_key.is_active = False
        test_api_key.save()

        api_client.credentials(HTTP_AUTHORIZATION=f"Api-Key {test_api_key.key}")
        response = api_client.get("/api/v1/quota/")
        assert response.status_code in (status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN)

    def test_authenticate_malformed_header_value(self, api_client):
        """Auth header without key value should return 401."""
        api_client.credentials(HTTP_AUTHORIZATION="Api-Key ")
        response = api_client.get("/api/v1/quota/")
        assert response.status_code in (status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN)

    def test_authenticate_wrong_keyword(self, api_client):
        """Using 'Bearer' instead of 'Api-Key' should return 401."""
        api_client.credentials(HTTP_AUTHORIZATION="Bearer some_token")
        response = api_client.get("/api/v1/quota/")
        assert response.status_code in (status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN)

    def test_authenticate_multiple_users(self, db):
        """Multiple users with valid keys should all authenticate."""
        from django.contrib.auth import get_user_model
        from gateway.models import APIKey
        import uuid

        User = get_user_model()

        user1 = User.objects.create_user(username="user1", password="pass1")
        key1 = APIKey.objects.create(
            user=user1,
            key=f"rg_test_{uuid.uuid4().hex[:32]}",
            name="Key 1",
        )

        user2 = User.objects.create_user(username="user2", password="pass2")
        key2 = APIKey.objects.create(
            user=user2,
            key=f"rg_test_{uuid.uuid4().hex[:32]}",
            name="Key 2",
        )

        client1 = APIClient()
        client1.credentials(HTTP_AUTHORIZATION=f"Api-Key {key1.key}")
        assert client1.get("/api/v1/quota/").status_code == status.HTTP_200_OK

        client2 = APIClient()
        client2.credentials(HTTP_AUTHORIZATION=f"Api-Key {key2.key}")
        assert client2.get("/api/v1/quota/").status_code == status.HTTP_200_OK

    def test_authenticate_nonexistent_key(self, api_client):
        """Random non-existent key should return 401."""
        api_client.credentials(
            HTTP_AUTHORIZATION="Api-Key rg_test_nonexistent_key_1234567890"
        )
        response = api_client.get("/api/v1/quota/")
        assert response.status_code in (status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN)

    def test_authenticate_key_with_spaces(self, api_client):
        """API key with leading/trailing spaces should still work."""
        from gateway.models import APIKey
        from django.contrib.auth import get_user_model
        import uuid

        User = get_user_model()
        user = User.objects.create_user(username="keyuser", password="pass")
        key = APIKey.objects.create(
            user=user,
            key=f"rg_test_{uuid.uuid4().hex[:32]}",
            name="Key with spaces",
        )

        api_client.credentials(HTTP_AUTHORIZATION=f"Api-Key  {key.key}  ")
        response = api_client.get("/api/v1/quota/")
        assert response.status_code == status.HTTP_200_OK


@pytest.mark.django_db
class TestAPIKeyModel:
    """Tests for the APIKey model."""

    def test_create_api_key(self, test_user):
        """Creating an API key should set defaults correctly."""
        from gateway.models import APIKey
        import uuid

        key = APIKey.objects.create(
            user=test_user,
            key=f"rg_test_{uuid.uuid4().hex[:32]}",
            name="Production Key",
        )
        assert key.is_active is True
        assert key.name == "Production Key"
        assert key.user == test_user

    def test_key_string_representation(self, test_user):
        """String representation should show name and key prefix."""
        from gateway.models import APIKey

        key = APIKey.objects.create(
            user=test_user,
            key="rg_test_abcdef1234567890abcdef1234567890",
            name="Dev Key",
        )
        str_repr = str(key)
        assert "Dev Key" in str_repr
        assert key.key[:8] in str_repr

    def test_key_is_unique(self, test_user):
        """Duplicate keys should be rejected."""
        from gateway.models import APIKey
        from django.db import IntegrityError

        APIKey.objects.create(
            user=test_user,
            key="unique_key_123",
            name="First",
        )

        with pytest.raises(IntegrityError):
            APIKey.objects.create(
                user=test_user,
                key="unique_key_123",
                name="Duplicate",
            )

    def test_delete_user_cascades_keys(self, test_user):
        """Deleting a user should cascade delete their API keys."""
        from gateway.models import APIKey
        import uuid

        APIKey.objects.create(
            user=test_user,
            key=f"rg_test_{uuid.uuid4().hex[:32]}",
            name="To be deleted",
        )

        test_user.delete()

        assert APIKey.objects.count() == 0

    def test_api_key_ordering(self, test_user):
        """API keys should be ordered by created_at descending."""
        from gateway.models import APIKey
        import uuid
        from django.utils import timezone
        from datetime import timedelta

        key1 = APIKey.objects.create(
            user=test_user,
            key=f"rg_test_{uuid.uuid4().hex[:32]}",
            name="Older Key",
        )
        key1.created_at = timezone.now() - timedelta(hours=1)
        key1.save()

        key2 = APIKey.objects.create(
            user=test_user,
            key=f"rg_test_{uuid.uuid4().hex[:32]}",
            name="Newer Key",
        )

        keys = APIKey.objects.all()
        assert keys[0].name == "Newer Key"
        assert keys[1].name == "Older Key"
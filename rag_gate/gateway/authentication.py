"""
Header-based static API key authentication for RAG-Gate.

Clients authenticate by passing their API key in the Authorization header:
    Authorization: Api-Key <key>

This is a machine-to-machine authentication mechanism, not session-based.
"""

from rest_framework import authentication
from rest_framework import exceptions

from .models import APIKey


class APIKeyAuthentication(authentication.BaseAuthentication):
    """
    DRF authentication class that validates static API keys.

    The key is read from the Authorization header with the 'Api-Key' prefix.
    """

    keyword = "Api-Key"

    def authenticate(self, request):
        auth_header = authentication.get_authorization_header(request)

        if not auth_header:
            return None  # No auth provided — let another auth class handle it

        try:
            auth_header_decoded = auth_header.decode("utf-8")
        except UnicodeDecodeError:
            raise exceptions.AuthenticationFailed("Invalid Authorization header encoding")

        if not auth_header_decoded.startswith(self.keyword):
            return None

        # Extract the key value
        try:
            _, key_value = auth_header_decoded.split(" ", 1)
        except ValueError:
            raise exceptions.AuthenticationFailed(
                "Invalid Authorization header format. Use: Authorization: Api-Key <key>"
            )

        key_value = key_value.strip()
        if not key_value:
            raise exceptions.AuthenticationFailed("API key is empty")

        try:
            api_key = APIKey.objects.select_related("user").get(
                key=key_value, is_active=True
            )
        except APIKey.DoesNotExist:
            raise exceptions.AuthenticationFailed("Invalid or inactive API key")

        return (api_key.user, api_key)
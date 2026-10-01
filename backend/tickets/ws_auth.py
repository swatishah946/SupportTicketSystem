"""Authenticate WebSocket connections with the same httpOnly JWT cookie as the REST API.

The browser sends cookies with the WebSocket handshake automatically (same
origin), so no token ever has to be exposed to JavaScript or put in the URL.
"""

from channels.db import database_sync_to_async
from channels.middleware import BaseMiddleware
from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
from django.http.cookie import parse_cookie
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.tokens import AccessToken


@database_sync_to_async
def user_from_token(raw):
    """Return (user, expiry_timestamp) for a valid access token, else (AnonymousUser, None)."""
    if not raw:
        return AnonymousUser(), None
    try:
        token = AccessToken(raw)  # checks signature and expiry
    except TokenError:
        return AnonymousUser(), None
    user = get_user_model().objects.filter(pk=token.get("user_id"), is_active=True).first()
    if user is None:
        return AnonymousUser(), None
    return user, token["exp"]


class JWTCookieAuthMiddleware(BaseMiddleware):
    async def __call__(self, scope, receive, send):
        headers = dict(scope.get("headers", []))
        cookies = parse_cookie(headers.get(b"cookie", b"").decode("latin-1"))
        user, expires_at = await user_from_token(cookies.get(settings.REST_AUTH["JWT_AUTH_COOKIE"]))
        scope = {**scope, "user": user, "token_expires_at": expires_at}
        return await super().__call__(scope, receive, send)

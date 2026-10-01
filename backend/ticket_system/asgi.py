"""ASGI entry point: normal HTTP requests go to Django, WebSocket connections to Channels.

    uvicorn ticket_system.asgi:application
"""

import os

from django.core.asgi import get_asgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "ticket_system.settings")

# Initialise Django before importing anything that touches models.
django_http = get_asgi_application()

from channels.routing import ProtocolTypeRouter, URLRouter  # noqa: E402
from channels.security.websocket import AllowedHostsOriginValidator  # noqa: E402
from django.urls import path  # noqa: E402

from tickets.consumers import NotificationConsumer  # noqa: E402
from tickets.ws_auth import JWTCookieAuthMiddleware  # noqa: E402

application = ProtocolTypeRouter({
    "http": django_http,
    # Origin check first: auth is cookie-based, so a page on another site must not
    # be able to open a socket that rides on our user's cookies.
    "websocket": AllowedHostsOriginValidator(
        JWTCookieAuthMiddleware(URLRouter([path("ws/", NotificationConsumer.as_asgi())]))
    ),
})

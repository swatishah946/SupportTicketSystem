"""One WebSocket per browser tab, used to push "something changed" notifications.

Each connection joins exactly one group:
  * agents and admins -> "staff"          (events for every ticket)
  * customers         -> "user_<id>"      (public events for their own tickets only)

Messages only say *what changed* (ticket id, kind of change, who did it). The
browser then re-fetches the ticket through the REST API, so all permission
rules stay in one place and nothing private can leak over the socket.
"""

import asyncio
import time

from channels.generic.websocket import AsyncJsonWebsocketConsumer

UNAUTHORIZED = 4401  # custom close code: the client should refresh its token and reconnect


def group_for(user):
    return "staff" if user.is_staff_member else f"user_{user.pk}"


class NotificationConsumer(AsyncJsonWebsocketConsumer):
    async def connect(self):
        user = self.scope.get("user")
        await self.accept()
        if user is None or not user.is_authenticated:
            # Accept-then-close so the browser sees our code (a rejected handshake hides it).
            await self.close(code=UNAUTHORIZED)
            return
        self.group = group_for(user)
        await self.channel_layer.group_add(self.group, self.channel_name)
        # The access token is short-lived. Close the socket when it expires so a
        # logged-out or disabled user stops receiving events; the client refreshes
        # its token and reconnects.
        expires_at = self.scope.get("token_expires_at")
        self.expiry = asyncio.create_task(self._close_at(expires_at)) if expires_at else None
        await self.send_json({"event": "connected", "role": user.role})

    async def _close_at(self, expires_at):
        await asyncio.sleep(max(0.0, expires_at - time.time()))
        await self.close(code=UNAUTHORIZED)

    async def disconnect(self, code):
        if getattr(self, "group", None):
            await self.channel_layer.group_discard(self.group, self.channel_name)
        if getattr(self, "expiry", None):
            self.expiry.cancel()

    async def receive_json(self, content, **kwargs):
        # Clients may send {"type": "ping"} as a keep-alive; nothing else is accepted.
        if content.get("type") == "ping":
            await self.send_json({"event": "pong"})

    async def ticket_event(self, message):
        """Handler for group messages of type "ticket.event"."""
        await self.send_json(message["data"])

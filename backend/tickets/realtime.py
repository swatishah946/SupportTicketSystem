"""Publish ticket changes to connected browsers (see consumers.py for who receives what)."""

import logging

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.db import transaction

log = logging.getLogger(__name__)


def publish(ticket, change, actor=None, internal=False, **extra):
    """Notify browsers that `ticket` changed.

    Sent only after the database transaction commits, so a browser that
    re-fetches straight away always sees the new data (and nothing is announced
    if the change is rolled back). Internal changes (private notes, escalations)
    go to staff only. Works from web requests and from Celery workers alike.
    """
    data = {
        "event": "ticket",
        "ticket": ticket.pk,
        "change": change,
        "title": ticket.title,
        "status": ticket.status,
        "assigned_to": ticket.assigned_to_id,
        "actor": actor.username if actor else "system",
        "actor_id": actor.pk if actor else None,
        **extra,
    }
    groups = ["staff"]
    if not internal and ticket.created_by_id:
        groups.append(f"user_{ticket.created_by_id}")

    def send():
        try:
            layer = get_channel_layer()
            for group in groups:
                async_to_sync(layer.group_send)(group, {"type": "ticket.event", "data": data})
        except Exception:  # live updates are best-effort; never fail the request
            log.exception("Failed to publish %s for ticket %s", change, ticket.pk)

    transaction.on_commit(send)

"""Live updates over WebSockets: authentication, origin check, and who receives what."""

import asyncio
from datetime import timedelta

import pytest
import pytest_asyncio
from channels.db import database_sync_to_async
from channels.layers import get_channel_layer
from channels.testing import WebsocketCommunicator
from django.db import connections
from django.utils import timezone
from rest_framework_simplejwt.tokens import AccessToken

from ticket_system.asgi import application
from tickets.models import Ticket, User
from tickets.services import workflow

from .conftest import make_ticket, make_user

pytestmark = [pytest.mark.asyncio, pytest.mark.django_db(transaction=True)]

db = database_sync_to_async


async def open_socket(user=None, origin="http://localhost:5173", token=None):
    headers = [(b"origin", origin.encode())]
    raw = token or (str(AccessToken.for_user(user)) if user else None)
    if raw:
        headers.append((b"cookie", f"nexus-access={raw}".encode()))
    socket = WebsocketCommunicator(application, "/ws/", headers=headers)
    connected, _ = await socket.connect()
    return socket, connected


async def ready(user):
    socket, connected = await open_socket(user)
    assert connected
    assert (await socket.receive_json_from())["event"] == "connected"
    return socket


@pytest_asyncio.fixture(autouse=True)
async def _fresh_layer():
    await get_channel_layer().flush()
    yield
    # Close the DB connection opened in the worker thread so Postgres can drop the test DB.
    await db(connections.close_all)()


async def test_no_cookie_is_closed_with_4401():
    socket, connected = await open_socket()
    assert connected  # accepted only so the client can read the close code
    assert (await socket.receive_output())["code"] == 4401


async def test_invalid_or_disabled_tokens_are_closed():
    socket, _ = await open_socket(token="not-a-jwt")
    assert (await socket.receive_output())["code"] == 4401

    user = await db(make_user)()
    token = str(AccessToken.for_user(user))
    user.is_active = False
    await db(user.save)()
    socket, _ = await open_socket(token=token)
    assert (await socket.receive_output())["code"] == 4401


async def test_other_site_cannot_open_a_socket():
    user = await db(make_user)()
    _, connected = await open_socket(user, origin="https://evil.example")
    assert not connected


async def test_customer_gets_public_updates_for_own_ticket_only():
    customer, other, agent = await db(make_user)(), await db(make_user)(), await db(make_user)(User.Role.AGENT)
    ticket = await db(make_ticket)(customer)
    mine, theirs = await ready(customer), await ready(other)

    await db(workflow.add_comment)(ticket, agent, "We're on it")
    event = await mine.receive_json_from()
    assert (event["ticket"], event["change"], event["actor"]) == (ticket.pk, "comment", agent.username)
    assert await theirs.receive_nothing()

    await db(workflow.add_comment)(ticket, agent, "VIP customer, be careful", is_internal=True)
    assert await mine.receive_nothing()  # private notes never reach the customer
    await mine.disconnect()
    await theirs.disconnect()


async def test_staff_get_everything_including_internal_events():
    customer, agent = await db(make_user)(), await db(make_user)(User.Role.AGENT)
    staff = await ready(agent)

    ticket = await db(workflow.create_ticket)(customer, "Export broken", "CSV export error 500")
    created = await staff.receive_json_from()
    assert (created["change"], created["ticket"], created["assigned_to"]) == ("created", ticket.pk, agent.pk)

    await db(workflow.add_comment)(ticket, agent, "check logs", is_internal=True)
    assert (await staff.receive_json_from())["change"] == "note"
    await staff.disconnect()


async def test_update_event_lists_changed_fields():
    customer, agent = await db(make_user)(), await db(make_user)(User.Role.AGENT)
    ticket = await db(make_ticket)(customer)
    socket = await ready(customer)
    await db(workflow.update_ticket)(ticket, agent, {"status": "resolved", "priority": "high"})
    event = await socket.receive_json_from()
    assert event["change"] == "updated" and set(event["fields"]) == {"status", "priority"}
    assert event["status"] == "resolved"
    await socket.disconnect()


async def test_escalation_from_background_job_reaches_staff_not_customer():
    customer, agent = await db(make_user)(), await db(make_user)(User.Role.AGENT)
    ticket = await db(make_ticket)(customer)
    await db(Ticket.objects.filter(pk=ticket.pk).update)(resolution_due=timezone.now() - timedelta(hours=1))
    staff, mine = await ready(agent), await ready(customer)

    await db(workflow.escalate_overdue)()
    assert (await staff.receive_json_from())["change"] == "escalated"
    assert await mine.receive_nothing()
    await staff.disconnect()
    await mine.disconnect()


async def test_socket_closes_when_access_token_expires():
    user = await db(make_user)()
    token = AccessToken.for_user(user)
    token.set_exp(lifetime=timedelta(seconds=1))
    socket, connected = await open_socket(token=str(token))
    assert connected and (await socket.receive_json_from())["event"] == "connected"
    await asyncio.sleep(1.2)
    assert (await socket.receive_output(timeout=2))["code"] == 4401


async def test_ping_pong():
    socket = await ready(await db(make_user)())
    await socket.send_json_to({"type": "ping"})
    assert await socket.receive_json_from() == {"event": "pong"}
    await socket.disconnect()

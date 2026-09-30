from datetime import timedelta

import pytest
from django.core.management import call_command
from django.utils import timezone

from tickets.models import Ticket, TicketEvent, User
from tickets.services import sla

from .conftest import client_for, make_ticket, make_user

pytestmark = pytest.mark.django_db


def create(client, **payload):
    body = {"title": "Payment failed", "description": "My card was declined at checkout"}
    body.update(payload)
    resp = client.post("/api/tickets/", body, format="json")
    assert resp.status_code == 201, resp.content
    return resp.json()


def test_create_sets_sla_and_ai_suggestion(customer):
    data = create(client_for(customer), priority="high")
    ticket = Ticket.objects.get(pk=data["id"])
    assert ticket.priority == "high"
    assert ticket.ai_category == "billing" and ticket.ai_source == "rules"
    assert ticket.resolution_due - ticket.created_at == timedelta(hours=24)
    assert ticket.first_response_due - ticket.created_at == timedelta(hours=4)
    assert data["sla_state"] == "on_track"
    assert [e["kind"] for e in data["events"]] == ["created"]


def test_create_without_triage_fields_uses_ai(customer):
    data = create(client_for(customer), title="Site down", description="Production is down for all users, outage")
    assert (data["category"], data["priority"]) == ("technical", "critical")


def test_auto_assigns_least_loaded_agent(customer):
    busy, idle = make_user(User.Role.AGENT), make_user(User.Role.AGENT)
    make_ticket(customer, assigned_to=busy)
    make_ticket(customer, assigned_to=busy, status="resolved")  # resolved work doesn't count
    make_ticket(customer, assigned_to=idle)
    make_ticket(customer, assigned_to=idle)
    data = create(client_for(customer))
    assert data["assigned_to"]["id"] == busy.id  # busy has 1 active, idle has 2


def test_no_agents_leaves_ticket_unassigned(customer):
    assert create(client_for(customer))["assigned_to"] is None


def test_first_agent_reply_records_first_response(customer, agent, ticket):
    client_for(customer).post(f"/api/tickets/{ticket.id}/comments/", {"body": "any update?"}, format="json")
    ticket.refresh_from_db()
    assert ticket.first_response_at is None  # customer replies don't count
    client_for(agent).post(f"/api/tickets/{ticket.id}/comments/", {"body": "on it"}, format="json")
    ticket.refresh_from_db()
    first = ticket.first_response_at
    assert first is not None and ticket.has_unread_updates
    client_for(agent).post(f"/api/tickets/{ticket.id}/comments/", {"body": "update"}, format="json")
    ticket.refresh_from_db()
    assert ticket.first_response_at == first


def test_internal_note_is_not_a_first_response(agent, ticket):
    client_for(agent).post(f"/api/tickets/{ticket.id}/comments/", {"body": "n", "is_internal": True}, format="json")
    ticket.refresh_from_db()
    assert ticket.first_response_at is None


def test_resolve_then_customer_reply_reopens(customer, agent, ticket):
    client_for(agent).patch(f"/api/tickets/{ticket.id}/", {"status": "resolved"}, format="json")
    ticket.refresh_from_db()
    assert ticket.resolved_at is not None
    client_for(customer).post(f"/api/tickets/{ticket.id}/comments/", {"body": "still broken"}, format="json")
    ticket.refresh_from_db()
    assert ticket.status == "open" and ticket.resolved_at is None


def test_invalid_transition_rejected(agent, ticket):
    Ticket.objects.filter(pk=ticket.pk).update(status="closed")
    resp = client_for(agent).patch(f"/api/tickets/{ticket.id}/", {"status": "resolved"}, format="json")
    assert resp.status_code == 400


def test_priority_change_recomputes_sla_and_is_audited(agent, ticket):
    client_for(agent).patch(f"/api/tickets/{ticket.id}/", {"priority": "critical"}, format="json")
    ticket.refresh_from_db()
    assert ticket.resolution_due - ticket.created_at == timedelta(hours=4)
    event = ticket.events.get(kind=TicketEvent.Kind.PRIORITY)
    assert (event.from_value, event.to_value, event.actor) == ("medium", "critical", agent)


def test_mark_duplicate_closes_ticket(customer, agent, ticket):
    original = make_ticket(customer)
    resp = client_for(agent).patch(f"/api/tickets/{ticket.id}/", {"duplicate_of_id": original.id}, format="json")
    assert resp.status_code == 200
    ticket.refresh_from_db()
    assert ticket.status == "closed" and ticket.duplicate_of == original
    self_dup = client_for(agent).patch(f"/api/tickets/{original.id}/", {"duplicate_of_id": original.id}, format="json")
    assert self_dup.status_code == 400


def test_customer_view_clears_unread_flag(customer, agent, ticket):
    client_for(agent).post(f"/api/tickets/{ticket.id}/comments/", {"body": "hi"}, format="json")
    client_for(customer).get(f"/api/tickets/{ticket.id}/")
    ticket.refresh_from_db()
    assert ticket.has_unread_updates is False


# --- SLA -------------------------------------------------------------------

def _ticket_at(customer, hours_ago, priority="medium", **extra):
    t = make_ticket(customer, priority=priority, **extra)
    created = timezone.now() - timedelta(hours=hours_ago)
    Ticket.objects.filter(pk=t.pk).update(created_at=created)
    t.refresh_from_db()
    sla.apply_sla(t)
    t.save()
    return t


def test_sla_states(customer):
    now = timezone.now()
    fresh = _ticket_at(customer, 0.1)
    assert sla.sla_state(fresh, now) == "on_track"
    late_response = _ticket_at(customer, 9)  # medium: 8h first-response window
    assert sla.sla_state(late_response, now) == "breached"
    responded = _ticket_at(customer, 40, first_response_at=now)  # 40/48h elapsed
    assert sla.sla_state(responded, now) == "at_risk"
    done = _ticket_at(customer, 10, resolved_at=now, status="resolved")
    assert sla.sla_state(done, now) == "met"
    Ticket.objects.filter(pk=done.pk).update(resolved_at=now + timedelta(days=5))
    done.refresh_from_db()
    assert sla.sla_state(done, now) == "breached"
    assert sla.sla_state(Ticket(), now) == "none"


def test_sla_breached_filter(customer, agent):
    _ticket_at(customer, 0.1)
    late = _ticket_at(customer, 9)
    resp = client_for(agent).get("/api/tickets/?sla_breached=true").json()
    assert [t["id"] for t in resp["results"]] == [late.id]


def test_escalate_overdue_is_idempotent(customer):
    late = _ticket_at(customer, 9, priority="medium")
    _ticket_at(customer, 0.1)
    call_command("escalate_overdue", stdout=open("/dev/null", "w"))
    late.refresh_from_db()
    assert (late.priority, late.escalated) == ("high", True)
    call_command("escalate_overdue", stdout=open("/dev/null", "w"))
    late.refresh_from_db()
    assert late.priority == "high"
    assert late.events.filter(kind=TicketEvent.Kind.ESCALATED).count() == 1


def test_escalate_dry_run_changes_nothing(customer):
    late = _ticket_at(customer, 9)
    call_command("escalate_overdue", "--dry-run", stdout=open("/dev/null", "w"))
    late.refresh_from_db()
    assert late.escalated is False


# --- listing -----------------------------------------------------------------

def test_list_filters_and_pagination(customer, agent):
    for i in range(25):
        make_ticket(customer, title=f"t{i}", assigned_to=agent if i % 5 == 0 else None)
    client = client_for(agent)
    page = client.get("/api/tickets/").json()
    assert page["count"] == 25 and len(page["results"]) == 20 and page["next"]
    assert client.get("/api/tickets/?assigned_to=me").json()["count"] == 5
    assert client.get("/api/tickets/?unassigned=true").json()["count"] == 20
    assert client.get("/api/tickets/?search=t13").json()["count"] == 1
    assert client.get("/api/tickets/?assigned_to=nobody").json()["count"] == 0
    assert client.get(f"/api/tickets/?assigned_to={agent.id}&active=true").json()["count"] == 5


# --- demo data -------------------------------------------------------------------

def test_seed_demo_builds_consistent_history():
    from django.core.management.base import CommandError
    from django.db.models import F

    with pytest.raises(CommandError):  # tests run with DEBUG off: guarded without --force
        call_command("seed_demo", tickets=1)
    call_command("seed_demo", tickets=60, force=True, stdout=open("/dev/null", "w"))
    call_command("seed_demo", tickets=10, force=True, stdout=open("/dev/null", "w"))  # users reused
    assert User.objects.filter(role=User.Role.AGENT).count() == 3
    assert Ticket.objects.count() == 70
    done = Ticket.objects.filter(status__in=Ticket.DONE_STATUSES)
    assert done.exists() and not done.filter(resolved_at__isnull=True).exists()
    assert not Ticket.objects.filter(resolution_due__isnull=True).exists()
    assert not Ticket.objects.filter(first_response_at__lt=F("created_at")).exists()

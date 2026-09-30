"""Background jobs: LLM triage off the request path, embedding retries, escalation."""

from datetime import timedelta

import pytest
from django.test import override_settings

from tickets import tasks
from tickets.models import Ticket, TicketEvent
from tickets.services import ai

from .conftest import client_for

pytestmark = pytest.mark.django_db


def _llm(category, priority):
    return lambda *a: ai.ClassificationSchema(category=category, priority=priority)


def test_create_does_not_wait_for_llm(monkeypatch, customer, django_capture_on_commit_callbacks):
    calls = []
    monkeypatch.setattr(ai, "_generate", lambda *a: calls.append(1) or ai.ClassificationSchema(
        category="account", priority="critical"))
    with override_settings(GEMINI_API_KEY="k"):
        with django_capture_on_commit_callbacks(execute=False) as callbacks:
            resp = client_for(customer).post("/api/tickets/", {"title": "Hi", "description": "cannot login"},
                                             format="json").json()
        assert calls == [] and len(callbacks) == 1  # request finished before any LLM call
        assert resp["priority"] != "critical"  # instant rule-based triage
        callbacks[0]()  # the worker runs the job
    ticket = Ticket.objects.get(pk=resp["id"])
    assert (ticket.priority, ticket.category, ticket.ai_source) == ("critical", "account", "llm")
    assert ticket.resolution_due - ticket.created_at == timedelta(hours=4)
    event = ticket.events.get(kind=TicketEvent.Kind.PRIORITY)
    assert event.actor is None  # attributed to the system in the audit trail


def test_llm_never_overrides_customer_choice(monkeypatch, customer, django_capture_on_commit_callbacks):
    monkeypatch.setattr(ai, "_generate", _llm("technical", "critical"))
    with override_settings(GEMINI_API_KEY="k"), django_capture_on_commit_callbacks(execute=True):
        resp = client_for(customer).post("/api/tickets/", {
            "title": "Hi", "description": "slow page", "priority": "low", "category": "general"}, format="json").json()
    ticket = Ticket.objects.get(pk=resp["id"])
    assert (ticket.priority, ticket.category) == ("low", "general")
    assert (ticket.ai_priority, ticket.ai_category) == ("critical", "technical")  # still recorded


def test_llm_never_overrides_an_agent(monkeypatch, customer, agent, django_capture_on_commit_callbacks):
    with django_capture_on_commit_callbacks(execute=False) as callbacks:
        resp = client_for(customer).post("/api/tickets/", {"title": "Hi", "description": "slow page"},
                                         format="json").json()
    client_for(agent).patch(f"/api/tickets/{resp['id']}/", {"priority": "high"}, format="json")
    monkeypatch.setattr(ai, "_generate", _llm("technical", "low"))
    with override_settings(GEMINI_API_KEY="k"):
        callbacks[0]()
    assert Ticket.objects.get(pk=resp["id"]).priority == "high"


def test_enrich_retries_transient_embedding_failures(monkeypatch, customer):
    ticket = Ticket.objects.create(title="t", description="d", category="general", priority="low",
                                   created_by=customer, ai_source="llm")
    attempts = []

    def flaky(text):
        attempts.append(1)
        if len(attempts) < 3:
            raise ConnectionError("provider hiccup")
        return [0.1, 0.2]

    monkeypatch.setattr(ai, "_embed", flaky)
    with override_settings(GEMINI_API_KEY="k"):
        tasks.enrich_ticket.apply(args=(ticket.pk, [])).get()  # eager apply runs retries inline
    ticket.refresh_from_db()
    assert len(attempts) == 3 and ticket.embedding == [0.1, 0.2]


def test_enrich_is_a_noop_without_ai_and_for_missing_tickets(customer):
    ticket = Ticket.objects.create(title="t", description="d", category="general", priority="low",
                                   created_by=customer, ai_source="rules")
    assert tasks.enrich_ticket.apply(args=(ticket.pk, ["priority"])).get() == "ok"
    ticket.refresh_from_db()
    assert ticket.embedding is None and ticket.ai_source == "rules"
    assert tasks.enrich_ticket.apply(args=(999999, [])).get() == "missing"


def test_escalation_task(customer):
    from django.utils import timezone

    late = Ticket.objects.create(title="t", description="d", category="general", priority="medium",
                                 created_by=customer)
    Ticket.objects.filter(pk=late.pk).update(resolution_due=timezone.now() - timedelta(hours=1))
    assert tasks.escalate_overdue.apply().get() == 1
    assert tasks.escalate_overdue.apply().get() == 0

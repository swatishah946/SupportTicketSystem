"""Customer satisfaction ratings and skills-based routing."""

import pytest

from tickets.models import Ticket, User
from tickets.services.assignment import least_loaded_agent

from .conftest import client_for, make_ticket, make_user

pytestmark = pytest.mark.django_db


def test_customer_rates_resolved_ticket_once(customer, agent, ticket):
    client = client_for(customer)
    early = client.post(f"/api/tickets/{ticket.id}/rate/", {"score": 5}, format="json")
    assert early.status_code == 400  # not resolved yet

    client_for(agent).patch(f"/api/tickets/{ticket.id}/", {"status": "resolved"}, format="json")
    resp = client.post(f"/api/tickets/{ticket.id}/rate/", {"score": 4, "comment": " quick fix "}, format="json")
    assert resp.status_code == 200
    body = resp.json()
    assert (body["csat_score"], body["csat_comment"]) == (4, "quick fix")
    assert body["events"][-1]["kind"] == "rated"
    assert client.post(f"/api/tickets/{ticket.id}/rate/", {"score": 1}, format="json").status_code == 400


@pytest.mark.parametrize("score", [0, 6, "great"])
def test_rating_is_validated(customer, ticket, score):
    Ticket.objects.filter(pk=ticket.pk).update(status="resolved")
    resp = client_for(customer).post(f"/api/tickets/{ticket.id}/rate/", {"score": score}, format="json")
    assert resp.status_code == 400


def test_only_the_ticket_owner_can_rate(agent, admin, ticket):
    Ticket.objects.filter(pk=ticket.pk).update(status="resolved")
    assert client_for(agent).post(f"/api/tickets/{ticket.id}/rate/", {"score": 5}, format="json").status_code == 403
    assert client_for(admin).post(f"/api/tickets/{ticket.id}/rate/", {"score": 5}, format="json").status_code == 403


def test_csat_in_analytics(customer, agent, admin):
    for score in (5, 4, 2):
        make_ticket(customer, status="resolved", assigned_to=agent, csat_score=score,
                    resolved_at="2026-01-01T00:00:00Z")
    make_ticket(customer, status="resolved", assigned_to=agent, resolved_at="2026-01-01T00:00:00Z")  # unrated
    data = client_for(admin).get("/api/analytics/").json()
    assert data["csat"] == {"responses": 3, "avg_score": 3.67, "satisfied_pct": 66.7, "response_rate_pct": 75.0}
    row = next(a for a in data["agents"] if a["id"] == agent.id)
    assert row["csat"] == 3.67


# --- routing ----------------------------------------------------------------------

def test_specialist_preferred_even_when_busier(customer):
    generalist = make_user(User.Role.AGENT)
    billing = make_user(User.Role.AGENT)
    billing.specialties = ["billing"]
    billing.save()
    make_ticket(customer, assigned_to=billing)  # specialist has more load
    assert least_loaded_agent("billing") == billing
    assert least_loaded_agent("technical") == generalist  # no specialist -> least loaded overall
    assert least_loaded_agent(None) == generalist


def test_least_loaded_among_specialists(customer):
    a, b = make_user(User.Role.AGENT), make_user(User.Role.AGENT)
    for agent in (a, b):
        agent.specialties = ["account"]
        agent.save()
    make_ticket(customer, assigned_to=a)
    assert least_loaded_agent("account") == b


def test_ticket_routed_to_specialist_on_create(customer):
    make_user(User.Role.AGENT)
    tech = make_user(User.Role.AGENT)
    tech.specialties = ["technical"]
    tech.save()
    resp = client_for(customer).post("/api/tickets/", {
        "title": "Crash", "description": "app crashes", "category": "technical"}, format="json").json()
    assert resp["assigned_to"]["id"] == tech.id


def test_admin_manages_specialties(admin, agent, customer):
    client = client_for(admin)
    resp = client.patch(f"/api/agents/{agent.id}/", {"specialties": ["technical", "billing", "billing"]},
                        format="json")
    assert resp.status_code == 200 and resp.json()["specialties"] == ["billing", "technical"]
    assert client.patch(f"/api/agents/{agent.id}/", {"specialties": ["cooking"]}, format="json").status_code == 400
    assert client.patch(f"/api/agents/{customer.id}/", {"specialties": []}, format="json").status_code == 404
    assert client_for(agent).patch(f"/api/agents/{agent.id}/", {"specialties": []},
                                   format="json").status_code == 403
    created = client.post("/api/auth/create-agent/", {
        "email": "spec@corp.com", "password": "Tr1cky-Horse-42", "specialties": ["account"]}, format="json")
    assert created.json()["specialties"] == ["account"]
    listed = client_for(agent).get("/api/agents/").json()
    assert next(a for a in listed if a["id"] == agent.id)["specialties"] == ["billing", "technical"]

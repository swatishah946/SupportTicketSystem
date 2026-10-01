"""Regression tests for the access-control holes found in the audit, plus
the rest of the permission matrix."""

import pytest

from tickets.models import Ticket, TicketComment, User

from .conftest import client_for, make_ticket

pytestmark = pytest.mark.django_db


def test_customer_cannot_promote_self_via_profile(customer):
    resp = client_for(customer).patch("/api/auth/user/", {"role": "admin"}, format="json")
    customer.refresh_from_db()
    assert resp.status_code == 200  # the endpoint works...
    assert customer.role == User.Role.CUSTOMER  # ...but role is read-only


def test_customer_cannot_change_own_email_via_profile(customer):
    client_for(customer).patch("/api/auth/user/", {"email": "evil@example.com"}, format="json")
    customer.refresh_from_db()
    assert customer.email != "evil@example.com"


@pytest.mark.parametrize("payload", [
    {"priority": "critical"},
    {"category": "billing"},
    {"status": "resolved"},
    {"resolution_notes": "fixed"},
])
def test_customer_cannot_change_triage_fields(customer, ticket, payload):
    resp = client_for(customer).patch(f"/api/tickets/{ticket.id}/", payload, format="json")
    assert resp.status_code == 403


def test_customer_cannot_assign_tickets(customer, other_customer, ticket):
    resp = client_for(customer).patch(f"/api/tickets/{ticket.id}/", {"assigned_to_id": other_customer.id},
                                      format="json")
    assert resp.status_code == 403
    ticket.refresh_from_db()
    assert ticket.assigned_to is None


def test_customer_can_close_and_edit_own_open_ticket(customer, ticket):
    client = client_for(customer)
    assert client.patch(f"/api/tickets/{ticket.id}/", {"title": "Better title"}, format="json").status_code == 200
    assert client.patch(f"/api/tickets/{ticket.id}/", {"status": "closed"}, format="json").status_code == 200
    ticket.refresh_from_db()
    assert (ticket.title, ticket.status) == ("Better title", "closed")


def test_customer_cannot_edit_ticket_once_in_progress(customer, ticket):
    Ticket.objects.filter(pk=ticket.pk).update(status="in_progress")
    resp = client_for(customer).patch(f"/api/tickets/{ticket.id}/", {"description": "x"}, format="json")
    assert resp.status_code == 403


def test_only_admin_can_delete(customer, agent, admin, ticket):
    assert client_for(customer).delete(f"/api/tickets/{ticket.id}/").status_code == 403
    assert client_for(agent).delete(f"/api/tickets/{ticket.id}/").status_code == 403
    assert client_for(admin).delete(f"/api/tickets/{ticket.id}/").status_code == 204


def test_customer_cannot_see_other_customers_tickets(customer, other_customer):
    theirs = make_ticket(other_customer)
    client = client_for(customer)
    assert client.get(f"/api/tickets/{theirs.id}/").status_code == 404
    assert client.get("/api/tickets/").json()["count"] == 0


def test_agent_cannot_assign_to_customer(agent, customer, ticket):
    resp = client_for(agent).patch(f"/api/tickets/{ticket.id}/", {"assigned_to_id": customer.id}, format="json")
    assert resp.status_code == 400


def test_internal_notes_hidden_from_customer(customer, agent, ticket):
    client_for(agent).post(f"/api/tickets/{ticket.id}/comments/",
                           {"body": "customer seems to be on old plan", "is_internal": True}, format="json")
    client_for(agent).post(f"/api/tickets/{ticket.id}/comments/", {"body": "Looking into it"}, format="json")

    customer_view = client_for(customer).get(f"/api/tickets/{ticket.id}/").json()
    assert [c["body"] for c in customer_view["comments"]] == ["Looking into it"]
    assert all(e["kind"] != "internal_note" for e in customer_view["events"])
    assert "ai_category" not in customer_view

    customer_list = client_for(customer).get("/api/tickets/").json()["results"][0]
    assert customer_list["comment_count"] == 1

    agent_view = client_for(agent).get(f"/api/tickets/{ticket.id}/").json()
    assert len(agent_view["comments"]) == 2


def test_customer_cannot_post_internal_note(customer, ticket):
    resp = client_for(customer).post(f"/api/tickets/{ticket.id}/comments/",
                                     {"body": "sneaky", "is_internal": True}, format="json")
    assert resp.status_code == 403
    assert not TicketComment.objects.exists()


def test_staff_only_and_admin_only_endpoints(customer, agent, ticket):
    assert client_for(customer).post(f"/api/tickets/{ticket.id}/suggest_reply/").status_code == 403
    assert client_for(customer).get("/api/agents/").status_code == 403
    assert client_for(agent).get("/api/analytics/").status_code == 403
    assert client_for(agent).post("/api/auth/create-agent/",
                                  {"email": "a@b.com", "password": "Very-long-pass1"}).status_code == 403


def test_admin_creates_agent_with_password_policy(admin):
    client = client_for(admin)
    weak = client.post("/api/auth/create-agent/", {"email": "new@corp.com", "password": "password"}, format="json")
    assert weak.status_code == 400
    ok = client.post("/api/auth/create-agent/", {"email": "new@corp.com", "password": "Tr1cky-Horse-42"}, format="json")
    assert ok.status_code == 201 and ok.json()["role"] == "support_agent"
    dup = client.post("/api/auth/create-agent/", {"email": "NEW@corp.com", "password": "Tr1cky-Horse-42"},
                      format="json")
    assert dup.status_code == 400


def test_anonymous_requests_rejected(db):
    from rest_framework.test import APIClient

    assert APIClient().get("/api/tickets/").status_code in (401, 403)
    assert APIClient().get("/api/health/").status_code == 200


def test_ai_endpoints_are_rate_limited(customer, monkeypatch):
    from rest_framework.throttling import ScopedRateThrottle

    monkeypatch.setattr(ScopedRateThrottle, "THROTTLE_RATES", {**ScopedRateThrottle.THROTTLE_RATES, "ai": "3/min"})
    client = client_for(customer)
    codes = [client.post("/api/tickets/classify/", {"description": f"error {i}"}, format="json").status_code
             for i in range(5)]
    assert codes == [200, 200, 200, 429, 429]

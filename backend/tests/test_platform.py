from datetime import timedelta

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.utils import timezone
from rest_framework.test import APIClient

from tickets.models import Ticket, TicketComment, User

from .conftest import client_for, make_ticket, make_user

pytestmark = pytest.mark.django_db


# --- performance ---------------------------------------------------------------

def _seed(n, customer, agent):
    for i in range(n):
        t = make_ticket(customer, title=f"t{i}", assigned_to=agent)
        TicketComment.objects.bulk_create([TicketComment(ticket=t, author=agent, body="x") for _ in range(3)])


def _queries(client, url):
    with CaptureQueriesContext(connection) as ctx:
        assert client.get(url).status_code == 200
    return len(ctx.captured_queries)


def test_ticket_list_query_count_is_constant(customer, agent):
    client = client_for(agent)
    _seed(5, customer, agent)
    small = _queries(client, "/api/tickets/?page_size=100")
    _seed(95, customer, agent)
    large = _queries(client, "/api/tickets/?page_size=100")
    assert small == large <= 3  # count + page (+ nothing per row)


def test_ticket_detail_query_count_is_constant(customer, agent):
    client = client_for(agent)
    t = make_ticket(customer)
    TicketComment.objects.create(ticket=t, author=agent, body="x")
    few = _queries(client, f"/api/tickets/{t.id}/")
    TicketComment.objects.bulk_create([TicketComment(ticket=t, author=customer, body="y") for _ in range(30)])
    many = _queries(client, f"/api/tickets/{t.id}/")
    assert few == many


# --- analytics -------------------------------------------------------------------

def test_analytics_numbers(customer, agent, admin):
    now = timezone.now()
    in_sla = make_ticket(customer, priority="high", assigned_to=agent, ai_category="technical", ai_priority="high")
    Ticket.objects.filter(pk=in_sla.pk).update(status="resolved", resolved_at=now,
                                               first_response_at=now, created_at=now - timedelta(hours=2))
    late = make_ticket(customer, priority="critical", ai_category="billing", ai_priority="critical")
    Ticket.objects.filter(pk=late.pk).update(created_at=now - timedelta(hours=10),
                                             resolution_due=now - timedelta(hours=6),
                                             first_response_due=now - timedelta(hours=9))
    data = client_for(admin).get("/api/analytics/").json()

    assert data["totals"]["total"] == 2
    assert data["totals"]["breached_active"] == 1
    assert data["totals"]["unassigned"] == 1
    assert data["sla"]["resolution_compliance_pct"] == 100.0
    assert data["sla"]["avg_resolution_minutes"] == pytest.approx(120, abs=1)
    assert data["ai"]["category_agreement_pct"] == 50.0  # 'late' was relabelled technical
    assert data["ai"]["priority_agreement_pct"] == 100.0
    assert len(data["daily_volume"]) == 14 and sum(d["count"] for d in data["daily_volume"]) == 2
    row = next(a for a in data["agents"] if a["id"] == agent.id)
    assert (row["active"], row["resolved_7d"]) == (0, 1)


def test_agent_directory(agent, admin, customer):
    ids = {u["id"] for u in client_for(agent).get("/api/agents/").json()}
    assert ids == {agent.id, admin.id}


# --- auth ----------------------------------------------------------------------

def test_signup_login_refresh_logout_with_httponly_cookies():
    client = APIClient()
    for email in ("alex@one.com", "alex@two.com"):  # same local part must not collide
        resp = client.post("/api/auth/registration/",
                           {"email": email, "password1": "Str0ng-pass-99", "password2": "Str0ng-pass-99"},
                           format="json")
        assert resp.status_code == 201, resp.content
        assert resp.cookies["nexus-access"]["httponly"]  # signed in straight away
    assert User.objects.filter(email__startswith="alex@").count() == 2
    assert set(User.objects.values_list("role", flat=True)) == {"customer"}

    client = APIClient()
    login = client.post("/api/auth/login/", {"email": "alex@one.com", "password": "Str0ng-pass-99"}, format="json")
    assert login.status_code == 200
    assert login.cookies["nexus-access"]["httponly"] and login.cookies["nexus-refresh"]["httponly"]
    assert login.json()["user"]["role"] == "customer"

    assert client.get("/api/auth/user/").status_code == 200  # authenticated by cookie alone
    refreshed = client.post("/api/auth/token/refresh/", {}, format="json")
    assert refreshed.status_code == 200
    assert client.post("/api/auth/logout/").status_code == 200
    assert APIClient().get("/api/auth/user/").status_code == 401


def test_openapi_schema_generates(db):
    resp = APIClient().get("/api/schema/")
    assert resp.status_code == 200 and b"/api/tickets/" in resp.content


def test_superuser_gets_admin_role(db):
    user = User.objects.create_superuser("root", "root@example.com", "pw-Long-enough-1")
    assert user.role == "admin" and user.is_admin
    with pytest.raises(ValueError):
        User.objects.create_user("x", "", "pw")
    with pytest.raises(ValueError):
        User.objects.create_superuser("y", "y@e.com", "pw", is_staff=False)
    assert make_user(User.Role.AGENT).is_staff_member

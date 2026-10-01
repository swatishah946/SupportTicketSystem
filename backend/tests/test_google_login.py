"""Sign in with Google (ID-token flow)."""

import pytest
from django.test import override_settings
from rest_framework.test import APIClient

from tickets import auth_views
from tickets.models import User

from .conftest import make_user

pytestmark = pytest.mark.django_db

CLIENT_ID = "1234-test.apps.googleusercontent.com"


def claims(**overrides):
    base = {"sub": "google-uid-1", "email": "Priya@Example.com", "email_verified": True,
            "given_name": "Priya", "family_name": "Shah", "aud": CLIENT_ID}
    base.update(overrides)
    return base


@pytest.fixture
def google(monkeypatch):
    """Replace Google's signature check with a fake that returns `google.claims`."""
    state = {"claims": claims(), "seen": []}

    def fake_verify(credential):
        state["seen"].append(credential)
        if credential == "bad":
            raise ValueError("Token used too late")
        return state["claims"]

    monkeypatch.setattr(auth_views, "verify_google_id_token", fake_verify)
    with override_settings(GOOGLE_CLIENT_ID=CLIENT_ID):
        yield state


def login(credential="good-token"):
    client = APIClient()
    return client, client.post("/api/auth/google/", {"credential": credential}, format="json")


def test_config_endpoint_exposes_only_the_public_client_id():
    assert APIClient().get("/api/auth/config/").json() == {"google_client_id": None}
    with override_settings(GOOGLE_CLIENT_ID=CLIENT_ID):
        assert APIClient().get("/api/auth/config/").json() == {"google_client_id": CLIENT_ID}


def test_not_configured_returns_503():
    _, resp = login()
    assert resp.status_code == 503


def test_first_google_login_creates_customer_and_sets_cookies(google):
    client, resp = login()
    assert resp.status_code == 200, resp.content
    user = User.objects.get(google_id="google-uid-1")
    assert (user.email, user.role, user.first_name) == ("priya@example.com", "customer", "Priya")
    assert not user.has_usable_password()  # cannot be logged into with a password
    assert resp.cookies["nexus-access"]["httponly"] and resp.cookies["nexus-refresh"]["httponly"]
    assert client.get("/api/auth/user/").json()["email"] == "priya@example.com"


def test_repeat_login_finds_same_user_even_if_email_changed(google):
    login()
    google["claims"] = claims(email="priya.new@example.com")
    _, resp = login()
    assert resp.json()["user"]["email"] == "priya@example.com"  # matched by Google id, not email
    assert User.objects.count() == 1


def test_links_existing_account_by_verified_email_and_keeps_role(google):
    agent = make_user(User.Role.AGENT, email="priya@example.com")
    _, resp = login()
    agent.refresh_from_db()
    assert agent.google_id == "google-uid-1"
    assert resp.json()["user"]["role"] == "support_agent"


def test_invalid_or_expired_token_rejected(google):
    _, resp = login("bad")
    assert resp.status_code == 400 and "invalid" in resp.json()["detail"]
    assert "nexus-access" not in resp.cookies


def test_unverified_email_rejected(google):
    google["claims"] = claims(email_verified=False)
    _, resp = login()
    assert resp.status_code == 400 and not User.objects.exists()


def test_disabled_account_rejected(google):
    user = make_user(email="priya@example.com")
    user.is_active = False
    user.save()
    _, resp = login()
    assert resp.status_code == 403


def test_missing_credential_is_a_validation_error(google):
    resp = APIClient().post("/api/auth/google/", {}, format="json")
    assert resp.status_code == 400 and google["seen"] == []


def test_real_verifier_checks_audience_is_our_client_id(monkeypatch):
    """The wrapper must pass our Client ID as the expected audience."""
    from google.oauth2 import id_token

    captured = {}

    def fake(token, request, audience=None, clock_skew_in_seconds=0):
        captured.update(token=token, audience=audience)
        return claims()

    monkeypatch.setattr(id_token, "verify_oauth2_token", fake)
    with override_settings(GOOGLE_CLIENT_ID=CLIENT_ID):
        auth_views.verify_google_id_token("abc")
    assert captured == {"token": "abc", "audience": CLIENT_ID}

import itertools

import pytest
from django.core.cache import cache
from rest_framework.test import APIClient

from tickets.models import Ticket, User
from tickets.services import sla

_seq = itertools.count(1)


@pytest.fixture(autouse=True)
def _clear_cache():
    cache.clear()
    yield
    cache.clear()


def make_user(role=User.Role.CUSTOMER, email=None):
    n = next(_seq)
    email = email or f"user{n}@example.com"
    return User.objects.create_user(f"user{n}", email, "S3cure-pass!", role=role)


def make_ticket(created_by, **kwargs):
    defaults = {"title": "Cannot export report", "description": "Export to CSV fails with error 500",
                "category": "technical", "priority": "medium"}
    defaults.update(kwargs)
    ticket = Ticket.objects.create(created_by=created_by, **defaults)
    sla.apply_sla(ticket)
    ticket.save()
    return ticket


def client_for(user):
    client = APIClient()
    client.force_authenticate(user)
    return client


@pytest.fixture
def customer(db):
    return make_user()


@pytest.fixture
def other_customer(db):
    return make_user()


@pytest.fixture
def agent(db):
    return make_user(User.Role.AGENT)


@pytest.fixture
def admin(db):
    return make_user(User.Role.ADMIN)


@pytest.fixture
def ticket(customer):
    return make_ticket(customer)

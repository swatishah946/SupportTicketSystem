"""SLA policy: deadlines per priority, live SLA state, escalation."""

from datetime import timedelta

from django.conf import settings
from django.db.models import Q
from django.utils import timezone


def deadlines_for(priority, start):
    first_h, resolve_h = settings.SLA_POLICY_HOURS[priority]
    return start + timedelta(hours=first_h), start + timedelta(hours=resolve_h)


def apply_sla(ticket, start=None):
    """(Re)compute deadlines. Deadlines always count from ticket creation, so
    raising the priority of an old ticket can immediately put it in breach."""
    start = start or ticket.created_at or timezone.now()
    ticket.first_response_due, ticket.resolution_due = deadlines_for(ticket.priority, start)


def sla_state(ticket, now=None):
    if not ticket.resolution_due:
        return "none"
    now = now or timezone.now()
    if ticket.resolved_at:
        return "met" if ticket.resolved_at <= ticket.resolution_due else "breached"
    if now > ticket.resolution_due:
        return "breached"
    if ticket.first_response_at is None and ticket.first_response_due and now > ticket.first_response_due:
        return "breached"
    window = (ticket.resolution_due - ticket.created_at).total_seconds() or 1
    elapsed = (now - ticket.created_at).total_seconds()
    return "at_risk" if elapsed / window >= settings.SLA_AT_RISK_FRACTION else "on_track"


def breached_q(now=None):
    """Queryset filter for active tickets currently in SLA breach."""
    now = now or timezone.now()
    from ..models import Ticket

    return Q(status__in=Ticket.ACTIVE_STATUSES) & (
        Q(resolution_due__lt=now) | Q(first_response_at__isnull=True, first_response_due__lt=now)
    )


PRIORITY_LADDER = ["low", "medium", "high", "critical"]


def next_priority(priority):
    idx = PRIORITY_LADDER.index(priority)
    return PRIORITY_LADDER[min(idx + 1, len(PRIORITY_LADDER) - 1)]

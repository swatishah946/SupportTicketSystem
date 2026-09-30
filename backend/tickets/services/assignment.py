"""Least-loaded auto-assignment.

Picks the support agent with the fewest active tickets in one aggregate query.
Ties go to the agent who has waited longest since their last assignment
(approximated by lowest id), which spreads work round-robin at equal load.
"""

from django.contrib.auth import get_user_model
from django.db.models import Count, Q


def least_loaded_agent():
    from ..models import Ticket

    User = get_user_model()
    return (
        User.objects.filter(role=User.Role.AGENT, is_active=True)
        .annotate(load=Count("assigned_tickets", filter=Q(assigned_tickets__status__in=Ticket.ACTIVE_STATUSES)))
        .order_by("load", "id")
        .first()
    )

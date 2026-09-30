"""Skills-aware, least-loaded auto-assignment.

Agents list the ticket categories they specialise in. A new ticket goes to the
least-loaded *specialist* for its category; if nobody specialises in it, to the
least-loaded agent overall. Load is the number of active tickets, computed for
every agent in one aggregate query. Ties go to the lowest id, which spreads work
round-robin at equal load.
"""

from django.contrib.auth import get_user_model
from django.db.models import Count, Q


def least_loaded_agent(category=None):
    from ..models import Ticket

    User = get_user_model()
    agents = list(
        User.objects.filter(role=User.Role.AGENT, is_active=True)
        .annotate(load=Count("assigned_tickets", filter=Q(assigned_tickets__status__in=Ticket.ACTIVE_STATUSES)))
        .order_by("load", "id")
    )
    # Filtered in Python: JSON list containment isn't portable across SQLite/Postgres,
    # and the agent list is small.
    specialists = [a for a in agents if category and category in (a.specialties or [])]
    pool = specialists or agents
    return pool[0] if pool else None

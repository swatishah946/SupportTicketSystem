"""Ticket lifecycle: creation, role-checked updates, comments.

All writes go through here so that permissions, the status state machine, SLA
timestamps and the audit trail are enforced in one place, whatever the entry
point (REST API, admin actions, management commands).
"""

from django.conf import settings
from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied, ValidationError

from ..models import Ticket, TicketComment, TicketEvent, User
from . import ai, sla
from .assignment import least_loaded_agent

# Which fields each role may change on an existing ticket.
EDITABLE_FIELDS = {
    User.Role.CUSTOMER: {"title", "description", "status"},
    User.Role.AGENT: {"status", "priority", "category", "assigned_to", "resolution_notes", "duplicate_of"},
    User.Role.ADMIN: {"status", "priority", "category", "assigned_to", "resolution_notes", "duplicate_of",
                      "title", "description"},
}


def log_event(ticket, actor, kind, from_value="", to_value=""):
    return TicketEvent.objects.create(
        ticket=ticket,
        actor=actor,
        kind=kind,
        from_value=str(from_value or "")[:200],
        to_value=str(to_value or "")[:200],
    )


@transaction.atomic
def create_ticket(user, title, description, category=None, priority=None):
    """Create a ticket without waiting on any AI provider.

    Triage uses the cached LLM answer or the instant rule-based one; the
    background job `tickets.tasks.enrich_ticket` then asks the LLM (if it wasn't
    already), applies its triage to fields the customer left to the AI, and
    stores the embedding used for semantic duplicate search.
    """
    suggestion = ai.classify_fast(title, description)
    ticket = Ticket(
        title=title,
        description=description,
        category=category or suggestion["category"],
        priority=priority or suggestion["priority"],
        created_by=user,
        ai_category=suggestion["category"],
        ai_priority=suggestion["priority"],
        ai_source=suggestion["source"],
    )
    ticket.save()  # created_at is set on insert; SLA counts from it
    sla.apply_sla(ticket)
    fields = ["first_response_due", "resolution_due"]
    if settings.AUTO_ASSIGN_TICKETS:
        agent = least_loaded_agent(ticket.category)
        if agent:
            ticket.assigned_to = agent
            fields.append("assigned_to")
    ticket.save(update_fields=fields)
    log_event(ticket, user, TicketEvent.Kind.CREATED, to_value=f"{ticket.category}/{ticket.priority}")
    if ticket.assigned_to:
        log_event(ticket, None, TicketEvent.Kind.ASSIGNED, to_value=ticket.assigned_to.email)

    from ..tasks import enrich_ticket  # local import: tasks imports this module

    ai_fields = [f for f, given in (("category", category), ("priority", priority)) if not given]
    transaction.on_commit(lambda: enrich_ticket.delay(ticket.pk, ai_fields))
    return ticket


def apply_ai_triage(ticket, suggestion, ai_fields):
    """Record an LLM suggestion and apply it to the fields the customer left to
    the AI, unless a human has already changed them. Returns changed fields."""
    changed = []
    ticket.ai_category, ticket.ai_priority, ticket.ai_source = (
        suggestion["category"], suggestion["priority"], suggestion["source"]
    )
    touched = set(ticket.events.filter(actor__isnull=False).values_list("kind", flat=True))
    if "category" in ai_fields and TicketEvent.Kind.CATEGORY not in touched \
            and suggestion["category"] != ticket.category:
        log_event(ticket, None, TicketEvent.Kind.CATEGORY, ticket.category, suggestion["category"])
        ticket.category = suggestion["category"]
        changed.append("category")
    if "priority" in ai_fields and TicketEvent.Kind.PRIORITY not in touched \
            and suggestion["priority"] != ticket.priority:
        log_event(ticket, None, TicketEvent.Kind.PRIORITY, ticket.priority, suggestion["priority"])
        ticket.priority = suggestion["priority"]
        sla.apply_sla(ticket)
        changed += ["priority", "first_response_due", "resolution_due"]
    ticket.save(update_fields=["ai_category", "ai_priority", "ai_source", *changed])
    return changed


def escalate_overdue(dry_run=False, now=None):
    """Bump the priority of active tickets past their SLA (once per ticket).

    Deadlines are kept: escalation raises urgency, it doesn't reset the clock
    on a ticket that is already late. Returns [(ticket_id, old, new)].
    """
    now = now or timezone.now()
    escalated = []
    with transaction.atomic():
        for ticket in Ticket.objects.filter(sla.breached_q(now), escalated=False).select_for_update():
            new_priority = sla.next_priority(ticket.priority)
            escalated.append((ticket.pk, ticket.priority, new_priority))
            if dry_run:
                continue
            log_event(ticket, None, TicketEvent.Kind.ESCALATED, ticket.priority, new_priority)
            ticket.priority = new_priority
            ticket.escalated = True
            ticket.save(update_fields=["priority", "escalated", "updated_at"])
    return escalated


def _set_status(ticket, new_status, actor, now):
    if not ticket.can_transition_to(new_status):
        raise ValidationError({"status": f"Cannot move a ticket from {ticket.status} to {new_status}."})
    old = ticket.status
    ticket.status = new_status
    if new_status in Ticket.DONE_STATUSES and not ticket.resolved_at:
        ticket.resolved_at = now
    elif new_status in Ticket.ACTIVE_STATUSES:
        ticket.resolved_at = None  # reopened
    log_event(ticket, actor, TicketEvent.Kind.STATUS, old, new_status)


@transaction.atomic
def update_ticket(ticket, user, changes):
    """Apply `changes` (already type-validated by the serializer) as `user`."""
    allowed = EDITABLE_FIELDS[user.role]
    forbidden = set(changes) - allowed
    if forbidden:
        raise PermissionDenied(f"Your role cannot change: {', '.join(sorted(forbidden))}.")

    if user.role == User.Role.CUSTOMER:
        if "status" in changes and changes["status"] != Ticket.Status.CLOSED:
            raise PermissionDenied("Customers can only close their own tickets.")
        if {"title", "description"} & set(changes) and ticket.status != Ticket.Status.OPEN:
            raise PermissionDenied("Tickets can only be edited while they are open.")

    now = timezone.now()
    customer_visible_change = False

    if "assigned_to" in changes:
        assignee = changes["assigned_to"]
        if assignee is not None and not assignee.is_staff_member:
            raise ValidationError({"assigned_to_id": "Tickets can only be assigned to agents or admins."})
        if assignee != ticket.assigned_to:
            log_event(ticket, user, TicketEvent.Kind.ASSIGNED,
                      ticket.assigned_to.email if ticket.assigned_to else "", assignee.email if assignee else "")
            ticket.assigned_to = assignee

    if "priority" in changes and changes["priority"] != ticket.priority:
        log_event(ticket, user, TicketEvent.Kind.PRIORITY, ticket.priority, changes["priority"])
        ticket.priority = changes["priority"]
        sla.apply_sla(ticket)
        customer_visible_change = True

    if "category" in changes and changes["category"] != ticket.category:
        log_event(ticket, user, TicketEvent.Kind.CATEGORY, ticket.category, changes["category"])
        ticket.category = changes["category"]

    if "duplicate_of" in changes and changes["duplicate_of"] != ticket.duplicate_of:
        original = changes["duplicate_of"]
        if original is not None:
            if original.pk == ticket.pk:
                raise ValidationError({"duplicate_of": "A ticket cannot duplicate itself."})
            log_event(ticket, user, TicketEvent.Kind.DUPLICATE, "", f"#{original.pk}")
            if ticket.status != Ticket.Status.CLOSED:
                _set_status(ticket, Ticket.Status.CLOSED, user, now)
            customer_visible_change = True
        ticket.duplicate_of = original

    if "status" in changes and changes["status"] != ticket.status:
        _set_status(ticket, changes["status"], user, now)
        customer_visible_change = True

    for field in ("title", "description", "resolution_notes"):
        if field in changes:
            setattr(ticket, field, changes[field])

    if customer_visible_change and user.is_staff_member:
        ticket.has_unread_updates = True
    ticket.save()
    return ticket


@transaction.atomic
def add_comment(ticket, user, body, is_internal=False):
    body = (body or "").strip()
    if not body:
        raise ValidationError({"body": "Comment body is required."})
    if is_internal and not user.is_staff_member:
        raise PermissionDenied("Only agents can add internal notes.")

    comment = TicketComment.objects.create(ticket=ticket, author=user, body=body, is_internal=is_internal)
    now = timezone.now()
    update_fields = ["updated_at"]

    if is_internal:
        log_event(ticket, user, TicketEvent.Kind.NOTE)
    else:
        log_event(ticket, user, TicketEvent.Kind.COMMENT)
        if user.is_staff_member:
            if ticket.first_response_at is None:
                ticket.first_response_at = now
                update_fields.append("first_response_at")
            ticket.has_unread_updates = True
            update_fields.append("has_unread_updates")
        elif ticket.status in Ticket.DONE_STATUSES:
            # Customer replied to a resolved ticket: it isn't resolved.
            _set_status(ticket, Ticket.Status.OPEN, user, now)
            update_fields += ["status", "resolved_at"]

    ticket.save(update_fields=update_fields)
    return comment


@transaction.atomic
def rate_ticket(ticket, user, score, comment=""):
    """Customer satisfaction rating: owner only, once, after resolution."""
    if ticket.created_by_id != user.pk:
        raise PermissionDenied("Only the customer who raised the ticket can rate it.")
    if ticket.status not in Ticket.DONE_STATUSES:
        raise ValidationError({"score": "Tickets can be rated once they are resolved."})
    if ticket.csat_score is not None:
        raise ValidationError({"score": "This ticket has already been rated."})
    ticket.csat_score = score
    ticket.csat_comment = (comment or "").strip()
    ticket.csat_at = timezone.now()
    ticket.save(update_fields=["csat_score", "csat_comment", "csat_at", "updated_at"])
    log_event(ticket, user, TicketEvent.Kind.RATED, to_value=f"{score}/5")
    return ticket


def resolution_text(ticket):
    """What fixed a resolved ticket: explicit notes, else the last public agent reply."""
    if ticket.resolution_notes:
        return ticket.resolution_notes
    staff_replies = [
        c.body for c in ticket.comments.all()
        if not c.is_internal and c.author.role in (User.Role.AGENT, User.Role.ADMIN)
    ]
    return staff_replies[-1] if staff_replies else ""

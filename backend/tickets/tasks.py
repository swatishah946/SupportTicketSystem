"""Background jobs.

Keeping LLM and embedding calls off the request path means creating a ticket
costs the same ~20 ms whether Gemini answers in 300 ms, 10 s, or not at all.
"""

import logging

from celery import shared_task
from django.db import transaction

from .models import Ticket
from .services import ai, workflow

log = logging.getLogger(__name__)


@shared_task(bind=True, autoretry_for=(Exception,), retry_backoff=True, retry_backoff_max=300, max_retries=4)
def enrich_ticket(self, ticket_id, ai_fields=()):
    """LLM triage + embedding for a freshly created ticket. Idempotent: safe to retry."""
    try:
        ticket = Ticket.objects.get(pk=ticket_id)
    except Ticket.DoesNotExist:
        return "missing"

    if ticket.ai_source != "llm":
        suggestion = ai.classify(ticket.title, ticket.description)
        if suggestion["source"] == "llm":
            with transaction.atomic():
                ticket = Ticket.objects.select_for_update().get(pk=ticket_id)
                changed = workflow.apply_ai_triage(ticket, suggestion, list(ai_fields))
            log.info("ticket %s triaged by LLM, changed %s", ticket_id, changed or "nothing")

    if ticket.embedding is None:
        # raise_errors: a transient provider failure is retried with backoff.
        vector = ai.embed(f"{ticket.title}\n{ticket.description}", raise_errors=True)
        if vector is not None:
            Ticket.objects.filter(pk=ticket_id).update(embedding=vector)
    return "ok"


@shared_task
def escalate_overdue():
    escalated = workflow.escalate_overdue()
    if escalated:
        log.info("escalated %d ticket(s): %s", len(escalated), escalated)
    return len(escalated)

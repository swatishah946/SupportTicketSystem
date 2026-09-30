"""Escalate active tickets that have breached their SLA.

Bumps priority one level (critical stays critical), flags the ticket as
escalated, unassigns nothing, and writes an audit event. Idempotent: an
already-escalated ticket is not bumped again.

Run on a schedule, e.g. every 5 minutes from cron / a scheduler container:
    python manage.py escalate_overdue
"""

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from tickets.models import Ticket, TicketEvent
from tickets.services.sla import breached_q, next_priority
from tickets.services.workflow import log_event


class Command(BaseCommand):
    help = "Escalate active tickets that are past their SLA."

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true")

    def handle(self, *args, dry_run=False, **options):
        now = timezone.now()
        overdue = Ticket.objects.filter(breached_q(now), escalated=False).select_for_update()
        count = 0
        with transaction.atomic():
            for ticket in overdue:
                new_priority = next_priority(ticket.priority)
                self.stdout.write(f"#{ticket.pk} {ticket.priority} -> {new_priority}")
                if dry_run:
                    continue
                log_event(ticket, None, TicketEvent.Kind.ESCALATED, ticket.priority, new_priority)
                # Keep the original deadlines: escalation raises urgency, it
                # doesn't reset the clock on a ticket that is already late.
                ticket.priority = new_priority
                ticket.escalated = True
                ticket.save(update_fields=["priority", "escalated", "updated_at"])
                count += 1
        self.stdout.write(self.style.SUCCESS(f"Escalated {count} ticket(s)."))

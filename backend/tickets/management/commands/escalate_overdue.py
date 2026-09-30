"""Escalate active tickets that have breached their SLA.

Runs automatically every 5 minutes via Celery beat (tickets.tasks.escalate_overdue);
this command is for manual runs and cron-only deployments:
    python manage.py escalate_overdue [--dry-run]
"""

from django.core.management.base import BaseCommand

from tickets.services.workflow import escalate_overdue


class Command(BaseCommand):
    help = "Escalate active tickets that are past their SLA."

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true")

    def handle(self, *args, dry_run=False, **options):
        results = escalate_overdue(dry_run=dry_run)
        for ticket_id, old, new in results:
            self.stdout.write(f"#{ticket_id} {old} -> {new}")
        verb = "Would escalate" if dry_run else "Escalated"
        self.stdout.write(self.style.SUCCESS(f"{verb} {len(results)} ticket(s)."))

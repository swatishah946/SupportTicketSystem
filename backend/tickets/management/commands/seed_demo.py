"""Seed a realistic demo workspace (users, tickets, conversations, SLA history).

    python manage.py seed_demo            # refuses to run with DEBUG off
    python manage.py seed_demo --tickets 500 --force

Demo accounts (password for all: DEMO_PASSWORD env var, default "NexusDemo!2026"):
    admin@nexusdesk.dev, agent1..3@nexusdesk.dev, customer1..8@nexusdesk.dev
"""

import json
import os
import random
from datetime import timedelta
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from tickets.models import Ticket, TicketComment, TicketEvent, User
from tickets.services import sla
from tickets.services.rules import classify_rules

DATASET = Path(settings.BASE_DIR) / "evals" / "tickets.jsonl"

AGENT_REPLIES = {
    "billing": "I've checked your billing history and corrected it. The adjustment will show within 5-7 working days.",
    "account": "I've reset the security settings on your account. Please sign in again and set a new password.",
    "technical": "We found the cause and deployed a fix. Please hard-refresh the page and try again.",
    "general": "Thanks for sharing this, I've passed it on to the product team.",
}


class Command(BaseCommand):
    help = "Create demo users and tickets for local development and screenshots."

    def add_arguments(self, parser):
        parser.add_argument("--tickets", type=int, default=120)
        parser.add_argument("--seed", type=int, default=7)
        parser.add_argument("--force", action="store_true", help="allow running with DEBUG off")

    def _user(self, email, role, password):
        user, created = User.objects.get_or_create(
            email=email, defaults={"username": email.split("@")[0], "role": role}
        )
        if created:
            user.set_password(password)
            user.is_staff = user.is_superuser = role == User.Role.ADMIN
            user.save()
        return user

    @transaction.atomic
    def handle(self, *args, tickets, seed, force, **options):
        if not settings.DEBUG and not force:
            raise CommandError("Refusing to seed demo data with DEBUG off (use --force).")
        rng = random.Random(seed)
        password = os.environ.get("DEMO_PASSWORD", "NexusDemo!2026")

        self._user("admin@nexusdesk.dev", User.Role.ADMIN, password)
        agents = [self._user(f"agent{i}@nexusdesk.dev", User.Role.AGENT, password) for i in range(1, 4)]
        customers = [self._user(f"customer{i}@nexusdesk.dev", User.Role.CUSTOMER, password) for i in range(1, 9)]
        rows = [json.loads(line) for line in DATASET.read_text().splitlines()]
        now = timezone.now()

        for i in range(tickets):
            row = rows[i % len(rows)]
            customer = rng.choice(customers)
            created = now - timedelta(days=rng.uniform(0, 14), hours=rng.uniform(0, 8))
            suggestion = classify_rules(f"{row['title']}\n{row['description']}")
            ticket = Ticket.objects.create(
                title=row["title"], description=row["description"], category=row["category"],
                priority=row["priority"], created_by=customer, ai_category=suggestion["category"],
                ai_priority=suggestion["priority"], ai_source="rules",
            )
            ticket.created_at = created
            sla.apply_sla(ticket, created)
            TicketEvent.objects.create(ticket=ticket, actor=customer, kind=TicketEvent.Kind.CREATED,
                                       to_value=f"{ticket.category}/{ticket.priority}", created_at=created)

            age_h = (now - created).total_seconds() / 3600
            if rng.random() < 0.85:
                ticket.assigned_to = rng.choice(agents)
            if ticket.assigned_to and rng.random() < 0.8:
                window = settings.SLA_POLICY_HOURS[ticket.priority][0]
                response_h = min(rng.uniform(0.05, window * 1.4), age_h)
                ticket.first_response_at = created + timedelta(hours=response_h)
                TicketComment.objects.create(ticket=ticket, author=ticket.assigned_to,
                                             body="Thanks for reporting this, I'm looking into it now.")
                ticket.status = Ticket.Status.IN_PROGRESS
                if age_h > 2 and rng.random() < 0.7:
                    resolve_h = min(rng.uniform(response_h, settings.SLA_POLICY_HOURS[ticket.priority][1] * 1.3),
                                    age_h)
                    ticket.resolved_at = created + timedelta(hours=resolve_h)
                    ticket.status = rng.choice([Ticket.Status.RESOLVED, Ticket.Status.CLOSED])
                    ticket.resolution_notes = AGENT_REPLIES[ticket.category]
                    TicketComment.objects.create(ticket=ticket, author=ticket.assigned_to,
                                                 body=AGENT_REPLIES[ticket.category])
            ticket.save()
            Ticket.objects.filter(pk=ticket.pk).update(created_at=created)

        self.stdout.write(self.style.SUCCESS(
            f"Seeded {tickets} tickets, {len(agents)} agents, {len(customers)} customers. Password: {password}"
        ))

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
        for agent, skills in zip(agents, (["billing"], ["technical"], ["account", "general"]), strict=True):
            agent.specialties = skills
            agent.save(update_fields=["specialties"])
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
            first_h, resolve_h = settings.SLA_POLICY_HOURS[ticket.priority]

            def event(kind, at, actor=None, old="", new="", _t=ticket):
                TicketEvent.objects.create(ticket=_t, actor=actor, kind=kind, from_value=old, to_value=new,
                                           created_at=at)

            def comment(body, author, at, _t=ticket):
                c = TicketComment.objects.create(ticket=_t, author=author, body=body)
                TicketComment.objects.filter(pk=c.pk).update(created_at=at)

            # A realistic team: old tickets are almost always done, open work skews recent.
            if rng.random() < (0.99 if age_h > 1 else 0.6):
                ticket.assigned_to = rng.choice(agents)
                event(TicketEvent.Kind.ASSIGNED, created + timedelta(minutes=1), new=ticket.assigned_to.email)
            if ticket.assigned_to and rng.random() < (0.99 if age_h > first_h else 0.5):
                response_h = min(rng.uniform(0.05, first_h * 1.3), age_h)
                replied = created + timedelta(hours=response_h)
                ticket.first_response_at = replied
                comment("Thanks for reporting this, I'm looking into it now.", ticket.assigned_to, replied)
                event(TicketEvent.Kind.COMMENT, replied, ticket.assigned_to)
                event(TicketEvent.Kind.STATUS, replied, ticket.assigned_to, "open", "in_progress")
                ticket.status = Ticket.Status.IN_PROGRESS
                if rng.random() < (0.96 if age_h > resolve_h else 0.4 if age_h > 2 else 0.0):
                    done_h = min(rng.uniform(response_h, resolve_h * 1.25), age_h)
                    done = created + timedelta(hours=done_h)
                    ticket.resolved_at = done
                    ticket.status = Ticket.Status.RESOLVED
                    ticket.resolution_notes = AGENT_REPLIES[ticket.category]
                    comment(AGENT_REPLIES[ticket.category], ticket.assigned_to, done)
                    event(TicketEvent.Kind.COMMENT, done, ticket.assigned_to)
                    event(TicketEvent.Kind.STATUS, done, ticket.assigned_to, "in_progress", "resolved")
                    if age_h - done_h > 48 and rng.random() < 0.6:
                        ticket.status = Ticket.Status.CLOSED
                        event(TicketEvent.Kind.STATUS, done + timedelta(hours=48), None, "resolved", "closed")
                    if rng.random() < 0.6:  # not every customer answers the survey
                        on_time = ticket.resolved_at <= ticket.resolution_due
                        ticket.csat_score = rng.choice([4, 5, 5] if on_time else [2, 3, 4])
                        ticket.csat_at = done + timedelta(hours=rng.uniform(0.2, 12))
                        event(TicketEvent.Kind.RATED, ticket.csat_at, customer, new=f"{ticket.csat_score}/5")
            ticket.save()
            Ticket.objects.filter(pk=ticket.pk).update(created_at=created)

        self.stdout.write(self.style.SUCCESS(
            f"Seeded {tickets} tickets, {len(agents)} agents, {len(customers)} customers. Password: {password}"
        ))

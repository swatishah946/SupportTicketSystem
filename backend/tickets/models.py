from django.conf import settings
from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils import timezone


class CustomUserManager(BaseUserManager):
    def create_user(self, username, email, password=None, **extra_fields):
        if not email:
            raise ValueError("The Email field must be set")
        if not username:
            raise ValueError("The Username field must be set")
        email = self.normalize_email(email)
        user = self.model(username=username, email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, username, email, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("role", User.Role.ADMIN)
        if extra_fields.get("is_staff") is not True:
            raise ValueError("Superuser must have is_staff=True.")
        if extra_fields.get("is_superuser") is not True:
            raise ValueError("Superuser must have is_superuser=True.")
        return self.create_user(username, email, password, **extra_fields)


class User(AbstractUser):
    class Role(models.TextChoices):
        CUSTOMER = "customer", "Customer"
        AGENT = "support_agent", "Support Agent"
        ADMIN = "admin", "Admin"

    role = models.CharField(max_length=20, choices=Role.choices, default=Role.CUSTOMER, db_index=True)
    # Ticket categories an agent specialises in; auto-assignment prefers specialists.
    specialties = models.JSONField(default=list, blank=True)
    # Google's permanent account id ("sub" claim), set on first Google sign-in.
    google_id = models.CharField(max_length=64, unique=True, null=True, blank=True)

    objects = CustomUserManager()

    @property
    def is_staff_member(self):
        return self.role in (self.Role.AGENT, self.Role.ADMIN)

    @property
    def is_admin(self):
        return self.role == self.Role.ADMIN


class Ticket(models.Model):
    class Category(models.TextChoices):
        BILLING = "billing", "Billing"
        TECHNICAL = "technical", "Technical"
        ACCOUNT = "account", "Account"
        GENERAL = "general", "General"

    class Priority(models.TextChoices):
        LOW = "low", "Low"
        MEDIUM = "medium", "Medium"
        HIGH = "high", "High"
        CRITICAL = "critical", "Critical"

    class Status(models.TextChoices):
        OPEN = "open", "Open"
        IN_PROGRESS = "in_progress", "In Progress"
        RESOLVED = "resolved", "Resolved"
        CLOSED = "closed", "Closed"

    ACTIVE_STATUSES = (Status.OPEN, Status.IN_PROGRESS)
    DONE_STATUSES = (Status.RESOLVED, Status.CLOSED)

    # Allowed status transitions (a small state machine).
    TRANSITIONS = {
        Status.OPEN: {Status.IN_PROGRESS, Status.RESOLVED, Status.CLOSED},
        Status.IN_PROGRESS: {Status.OPEN, Status.RESOLVED, Status.CLOSED},
        Status.RESOLVED: {Status.OPEN, Status.IN_PROGRESS, Status.CLOSED},
        Status.CLOSED: {Status.OPEN},
    }

    title = models.CharField(max_length=200)
    description = models.TextField()
    category = models.CharField(max_length=20, choices=Category.choices)
    priority = models.CharField(max_length=20, choices=Priority.choices)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.OPEN)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="tickets_created", null=True, blank=True
    )
    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="assigned_tickets"
    )
    resolution_notes = models.TextField(blank=True, null=True)
    has_unread_updates = models.BooleanField(default=False)

    # SLA tracking
    first_response_due = models.DateTimeField(null=True, blank=True)
    resolution_due = models.DateTimeField(null=True, blank=True)
    first_response_at = models.DateTimeField(null=True, blank=True)
    resolved_at = models.DateTimeField(null=True, blank=True)
    escalated = models.BooleanField(default=False)

    # What the AI suggested at creation time, kept so we can measure how often
    # humans agree with it (and so a bad model version is detectable).
    ai_category = models.CharField(max_length=20, choices=Category.choices, blank=True)
    ai_priority = models.CharField(max_length=20, choices=Priority.choices, blank=True)
    ai_source = models.CharField(max_length=10, blank=True)  # "llm" | "rules"

    # Semantic embedding of title+description (Gemini), when available.
    embedding = models.JSONField(null=True, blank=True, editable=False)

    # Customer satisfaction, collected once the ticket is resolved.
    csat_score = models.PositiveSmallIntegerField(
        null=True, blank=True, validators=[MinValueValidator(1), MaxValueValidator(5)]
    )
    csat_comment = models.TextField(blank=True)
    csat_at = models.DateTimeField(null=True, blank=True)

    duplicate_of = models.ForeignKey(
        "self", on_delete=models.SET_NULL, null=True, blank=True, related_name="duplicates"
    )

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["status", "priority"]),
            models.Index(fields=["assigned_to", "status"]),
            models.Index(fields=["created_by", "-created_at"]),
            models.Index(fields=["resolution_due"]),
        ]

    def __str__(self):
        return f"#{self.pk} {self.title} ({self.status})"

    def can_transition_to(self, new_status):
        return new_status == self.status or new_status in self.TRANSITIONS.get(self.status, set())

    @property
    def sla_state(self):
        """on_track | at_risk | breached | met | none"""
        from .services.sla import sla_state

        return sla_state(self)


class TicketComment(models.Model):
    ticket = models.ForeignKey(Ticket, on_delete=models.CASCADE, related_name="comments")
    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    body = models.TextField()
    # Internal notes are visible to agents/admins only.
    is_internal = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]

    def __str__(self):
        return f"Comment by {self.author.email} on #{self.ticket_id}"


class TicketEvent(models.Model):
    """Append-only audit trail: who changed what, and when."""

    class Kind(models.TextChoices):
        CREATED = "created", "Created"
        STATUS = "status_changed", "Status changed"
        PRIORITY = "priority_changed", "Priority changed"
        CATEGORY = "category_changed", "Category changed"
        ASSIGNED = "assigned", "Assigned"
        COMMENT = "commented", "Commented"
        NOTE = "internal_note", "Internal note"
        ESCALATED = "escalated", "Escalated"
        DUPLICATE = "marked_duplicate", "Marked duplicate"
        RATED = "rated", "Rated"

    # Events customers never see.
    INTERNAL_KINDS = {Kind.NOTE, Kind.ESCALATED}

    ticket = models.ForeignKey(Ticket, on_delete=models.CASCADE, related_name="events")
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    kind = models.CharField(max_length=30, choices=Kind.choices)
    from_value = models.CharField(max_length=200, blank=True)
    to_value = models.CharField(max_length=200, blank=True)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["created_at", "id"]

    def __str__(self):
        return f"{self.kind} on #{self.ticket_id}"

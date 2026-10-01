from datetime import timedelta

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import connection
from django.db.models import Avg, Count, DurationField, ExpressionWrapper, F, Prefetch, Q
from django.db.models.functions import TruncDate
from django.utils import timezone
from django_filters.rest_framework import DjangoFilterBackend
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema
from rest_framework import filters, mixins, permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response
from rest_framework.views import APIView

from .adapters import unique_username
from .filters import TicketFilter
from .models import Ticket, TicketComment, TicketEvent
from .permissions import IsAdminRole, IsStaffMember
from .serializers import (
    AgentSerializer,
    CommentInputSerializer,
    CreateAgentSerializer,
    RatingSerializer,
    TextInputSerializer,
    TicketCommentSerializer,
    TicketDetailSerializer,
    TicketListSerializer,
    TicketWriteSerializer,
)
from .services import ai, workflow
from .services.search import rank, ticket_text
from .services.sla import breached_q

User = get_user_model()



def _embedding_of(ticket):
    return ticket.embedding


def find_similar(query, candidates, top_k, lexical_threshold, hybrid_threshold):
    """Hybrid (semantic + lexical) when an embedding is available, lexical otherwise."""
    query_embedding = ai.embed(query)
    threshold = hybrid_threshold if query_embedding else lexical_threshold
    return rank(query, candidates, ticket_text, top_k=top_k, min_score=threshold,
                query_embedding=query_embedding, embedding_of=_embedding_of)


class TicketViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, mixins.CreateModelMixin,
                    mixins.UpdateModelMixin, mixins.DestroyModelMixin, viewsets.GenericViewSet):
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_class = TicketFilter
    search_fields = ["title", "description"]
    ordering_fields = ["created_at", "updated_at", "priority", "resolution_due"]
    ordering = ["-created_at"]

    def get_serializer_class(self):
        if self.action in ("create", "update", "partial_update"):
            return TicketWriteSerializer
        return TicketDetailSerializer if self.action == "retrieve" else TicketListSerializer

    def get_throttles(self):
        if self.action in ("classify", "suggest_reply"):
            self.throttle_scope = "ai"
        return super().get_throttles()

    queryset = Ticket.objects.none()  # for schema generation; real scoping below

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return Ticket.objects.none()
        user = self.request.user
        qs = Ticket.objects.select_related("created_by", "assigned_to")
        if self.action not in ("similar", "suggest_reply"):
            qs = qs.defer("embedding")  # vectors are only needed for retrieval
        if not user.is_staff_member:
            qs = qs.filter(created_by=user)

        public = Q(comments__is_internal=False)
        if self.action == "list":
            # One COUNT per page instead of one query per ticket.
            qs = qs.annotate(comment_count=Count("comments", filter=None if user.is_staff_member else public))
        elif self.action == "retrieve":
            comments = TicketComment.objects.select_related("author")
            events = TicketEvent.objects.select_related("actor")
            if not user.is_staff_member:
                comments = comments.filter(is_internal=False)
                events = events.exclude(kind__in=TicketEvent.INTERNAL_KINDS)
            qs = qs.prefetch_related(Prefetch("comments", queryset=comments), Prefetch("events", queryset=events))
        return qs

    def _detail(self, ticket, code=status.HTTP_200_OK):
        # Re-read through the retrieve queryset so permissions/prefetches apply.
        self.action = "retrieve"
        fresh = self.get_queryset().get(pk=ticket.pk)
        return Response(TicketDetailSerializer(fresh, context=self.get_serializer_context()).data, status=code)

    def retrieve(self, request, *args, **kwargs):
        ticket = self.get_object()
        if not request.user.is_staff_member and ticket.has_unread_updates:
            Ticket.objects.filter(pk=ticket.pk).update(has_unread_updates=False)
            ticket.has_unread_updates = False
        return Response(self.get_serializer(ticket).data)

    def create(self, request, *args, **kwargs):
        serializer = TicketWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        ticket = workflow.create_ticket(
            request.user, data["title"], data["description"], data.get("category"), data.get("priority")
        )
        return self._detail(ticket, status.HTTP_201_CREATED)

    def update(self, request, *args, **kwargs):
        ticket = self.get_object()
        serializer = TicketWriteSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        workflow.update_ticket(ticket, request.user, serializer.validated_data)
        return self._detail(ticket)

    def destroy(self, request, *args, **kwargs):
        if not request.user.is_admin:
            raise PermissionDenied("Only admins can delete tickets.")
        return super().destroy(request, *args, **kwargs)

    @extend_schema(request=CommentInputSerializer, responses=TicketCommentSerializer)
    @action(detail=True, methods=["post"])
    def comments(self, request, pk=None):
        ticket = self.get_object()
        data = CommentInputSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        comment = workflow.add_comment(ticket, request.user, data.validated_data["body"],
                                       data.validated_data["is_internal"])
        return Response(TicketCommentSerializer(comment).data, status=status.HTTP_201_CREATED)

    @extend_schema(request=RatingSerializer, responses=TicketDetailSerializer)
    @action(detail=True, methods=["post"])
    def rate(self, request, pk=None):
        """Customer satisfaction rating (1-5) once the ticket is resolved."""
        ticket = self.get_object()
        data = RatingSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        workflow.rate_ticket(ticket, request.user, data.validated_data["score"], data.validated_data["comment"])
        return self._detail(ticket)

    @extend_schema(request=TextInputSerializer)
    @action(detail=False, methods=["post"])
    def classify(self, request):
        """AI triage suggestion for a draft ticket (LLM, with rule-based fallback)."""
        data = TextInputSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        return Response(ai.classify(data.validated_data["title"], data.validated_data["description"]))

    @extend_schema(request=TextInputSerializer)
    @action(detail=False, methods=["post"])
    def similar(self, request):
        """Possible duplicates among the caller's visible active tickets (hybrid retrieval)."""
        data = TextInputSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        candidates = self.get_queryset().filter(status__in=Ticket.ACTIVE_STATUSES)
        exclude = request.query_params.get("exclude")
        if exclude and exclude.isdigit():
            candidates = candidates.exclude(pk=int(exclude))
        query = f"{data.validated_data['title']} {data.validated_data['description']}"
        matches = find_similar(query, candidates[:1000], 3,
                               settings.DUPLICATE_THRESHOLD_LEXICAL, settings.DUPLICATE_THRESHOLD_HYBRID)
        return Response([
            {"id": t.id, "title": t.title, "status": t.status, "score": score} for t, score in matches
        ])

    @action(detail=True, methods=["post"], permission_classes=[IsStaffMember])
    def suggest_reply(self, request, pk=None):
        """Draft a reply grounded in the most similar resolved tickets (RAG)."""
        ticket = self.get_object()
        resolved = (
            Ticket.objects.filter(status__in=Ticket.DONE_STATUSES)
            .exclude(pk=ticket.pk)
            .prefetch_related(Prefetch("comments", queryset=TicketComment.objects.select_related("author")))
            .order_by("-resolved_at")[:500]
        )
        ranked = find_similar(f"{ticket.title}\n{ticket.description}", resolved, 5,
                              settings.GROUNDING_THRESHOLD, settings.GROUNDING_THRESHOLD)
        similar = [(t, s, workflow.resolution_text(t)) for t, s in ranked]
        similar = [item for item in similar if item[2]][:3]
        conversation = [
            ("Agent" if c.author.is_staff_member else "Customer", c.body)
            for c in ticket.comments.select_related("author").filter(is_internal=False)
        ]
        return Response(ai.draft_reply(ticket, conversation, similar))


TOTAL_KEYS = ("total", "open", "in_progress", "resolved", "unassigned", "breached_active", "escalated_active")


class AnalyticsView(APIView):
    permission_classes = [IsAdminRole]

    @extend_schema(responses=OpenApiTypes.OBJECT)
    def get(self, request):
        now = timezone.now()
        tickets = Ticket.objects.all()

        totals = tickets.aggregate(
            total=Count("id"),
            open=Count("id", filter=Q(status=Ticket.Status.OPEN)),
            in_progress=Count("id", filter=Q(status=Ticket.Status.IN_PROGRESS)),
            resolved=Count("id", filter=Q(status__in=Ticket.DONE_STATUSES)),
            unassigned=Count("id", filter=Q(status__in=Ticket.ACTIVE_STATUSES, assigned_to__isnull=True)),
            breached_active=Count("id", filter=breached_q(now)),
            escalated_active=Count("id", filter=Q(escalated=True, status__in=Ticket.ACTIVE_STATUSES)),
            resolved_count=Count("id", filter=Q(resolved_at__isnull=False)),
            resolved_in_sla=Count("id", filter=Q(resolved_at__isnull=False, resolved_at__lte=F("resolution_due"))),
            responded=Count("id", filter=Q(first_response_at__isnull=False)),
            responded_in_sla=Count("id", filter=Q(first_response_at__lte=F("first_response_due"))),
            ai_labelled=Count("id", filter=~Q(ai_category="")),
            ai_category_kept=Count("id", filter=~Q(ai_category="") & Q(category=F("ai_category"))),
            ai_priority_kept=Count("id", filter=~Q(ai_priority="") & Q(priority=F("ai_priority"))),
            csat_responses=Count("id", filter=Q(csat_score__isnull=False)),
            csat_satisfied=Count("id", filter=Q(csat_score__gte=4)),
            csat_avg=Avg("csat_score"),
            avg_first_response=Avg(ExpressionWrapper(F("first_response_at") - F("created_at"),
                                                     output_field=DurationField())),
            avg_resolution=Avg(ExpressionWrapper(F("resolved_at") - F("created_at"), output_field=DurationField())),
        )

        def pct(num, den):
            return round(100 * num / den, 1) if den else None

        def minutes(delta):
            return round(delta.total_seconds() / 60, 1) if delta else None

        since = now - timedelta(days=13)
        daily = (
            tickets.filter(created_at__date__gte=since.date())
            .annotate(day=TruncDate("created_at")).values("day").annotate(count=Count("id")).order_by("day")
        )
        daily_map = {row["day"].isoformat(): row["count"] for row in daily}
        volume = [
            {"date": (since.date() + timedelta(days=i)).isoformat(),
             "count": daily_map.get((since.date() + timedelta(days=i)).isoformat(), 0)}
            for i in range(14)
        ]

        week_ago = now - timedelta(days=7)
        agents = (
            User.objects.filter(role__in=[User.Role.AGENT, User.Role.ADMIN], is_active=True)
            .annotate(
                active=Count("assigned_tickets", filter=Q(assigned_tickets__status__in=Ticket.ACTIVE_STATUSES)),
                resolved_7d=Count("assigned_tickets", filter=Q(assigned_tickets__resolved_at__gte=week_ago)),
                breached=Count("assigned_tickets", filter=Q(
                    assigned_tickets__status__in=Ticket.ACTIVE_STATUSES,
                    assigned_tickets__resolution_due__lt=now,
                )),
                csat=Avg("assigned_tickets__csat_score"),
            )
            .order_by("-active", "username")
        )

        def breakdown(field):
            return {row[field]: row["n"] for row in tickets.values(field).annotate(n=Count("id")).order_by()}

        return Response({
            "totals": {k: totals[k] for k in TOTAL_KEYS},
            "sla": {
                "resolution_compliance_pct": pct(totals["resolved_in_sla"], totals["resolved_count"]),
                "first_response_compliance_pct": pct(totals["responded_in_sla"], totals["responded"]),
                "avg_first_response_minutes": minutes(totals["avg_first_response"]),
                "avg_resolution_minutes": minutes(totals["avg_resolution"]),
            },
            "csat": {
                "responses": totals["csat_responses"],
                "avg_score": round(totals["csat_avg"], 2) if totals["csat_avg"] is not None else None,
                "satisfied_pct": pct(totals["csat_satisfied"], totals["csat_responses"]),
                "response_rate_pct": pct(totals["csat_responses"], totals["resolved_count"]),
            },
            "ai": {
                "labelled_tickets": totals["ai_labelled"],
                "category_agreement_pct": pct(totals["ai_category_kept"], totals["ai_labelled"]),
                "priority_agreement_pct": pct(totals["ai_priority_kept"], totals["ai_labelled"]),
            },
            "by_priority": breakdown("priority"),
            "by_category": breakdown("category"),
            "by_status": breakdown("status"),
            "daily_volume": volume,
            "agents": [
                {"id": a.id, "username": a.username, "email": a.email, "role": a.role,
                 "active": a.active, "resolved_7d": a.resolved_7d, "breached": a.breached,
                 "csat": round(a.csat, 2) if a.csat is not None else None, "specialties": a.specialties or []}
                for a in agents
            ],
        })


class AgentListView(APIView):
    """Staff directory for the reassignment dropdown."""

    permission_classes = [IsStaffMember]

    @extend_schema(responses=AgentSerializer(many=True))
    def get(self, request):
        staff = User.objects.filter(role__in=[User.Role.AGENT, User.Role.ADMIN], is_active=True).order_by("username")
        return Response(AgentSerializer(staff, many=True).data)


class AgentDetailView(APIView):
    """Admins set which ticket categories an agent specialises in."""

    permission_classes = [IsAdminRole]

    @extend_schema(request=AgentSerializer, responses=AgentSerializer)
    def patch(self, request, pk):
        agent = User.objects.filter(pk=pk, role__in=[User.Role.AGENT, User.Role.ADMIN]).first()
        if agent is None:
            return Response({"detail": "Agent not found."}, status=status.HTTP_404_NOT_FOUND)
        serializer = AgentSerializer(agent, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)


class CreateAgentView(APIView):
    permission_classes = [IsAdminRole]
    throttle_scope = "auth"

    @extend_schema(request=CreateAgentSerializer, responses={201: AgentSerializer})
    def post(self, request):
        data = CreateAgentSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        email = User.objects.normalize_email(data.validated_data["email"]).lower()
        password = data.validated_data["password"]
        if User.objects.filter(email__iexact=email).exists():
            return Response({"email": ["A user with this email already exists."]}, status=status.HTTP_400_BAD_REQUEST)
        try:
            validate_password(password)
        except DjangoValidationError as exc:
            return Response({"password": list(exc.messages)}, status=status.HTTP_400_BAD_REQUEST)
        agent = User.objects.create_user(unique_username(email), email, password, role=User.Role.AGENT,
                                         specialties=sorted(set(data.validated_data["specialties"])))
        return Response(AgentSerializer(agent).data, status=status.HTTP_201_CREATED)


class HealthView(APIView):
    """Liveness + DB check for container orchestration."""

    permission_classes = [permissions.AllowAny]
    authentication_classes = []
    throttle_classes = []

    @extend_schema(responses=OpenApiTypes.OBJECT)
    def get(self, request):
        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
            db = "ok"
        except Exception:  # pragma: no cover
            db = "unavailable"
        code = status.HTTP_200_OK if db == "ok" else status.HTTP_503_SERVICE_UNAVAILABLE
        return Response({"status": "ok" if db == "ok" else "degraded", "database": db}, status=code)

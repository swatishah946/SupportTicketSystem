from dj_rest_auth.registration.serializers import RegisterSerializer
from rest_framework import serializers

from .models import Ticket, TicketComment, TicketEvent, User


class CustomRegisterSerializer(RegisterSerializer):
    username = None

    def get_cleaned_data(self):
        data = super().get_cleaned_data()
        data.pop("username", None)
        return data


class UserSerializer(serializers.ModelSerializer):
    """Used by /api/auth/user/. Role and email are read-only: a user must never
    be able to promote themselves by PATCHing their own profile."""

    class Meta:
        model = User
        fields = ["id", "username", "email", "role"]
        read_only_fields = ["id", "email", "role"]


class UserMiniSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ["id", "username", "email", "role"]
        read_only_fields = fields


class AgentSerializer(serializers.ModelSerializer):
    specialties = serializers.ListField(
        child=serializers.ChoiceField(choices=Ticket.Category.choices), required=False, allow_empty=True
    )

    class Meta:
        model = User
        fields = ["id", "username", "email", "role", "specialties"]
        read_only_fields = ["id", "username", "email", "role"]

    def validate_specialties(self, value):
        return sorted(set(value))


class TicketCommentSerializer(serializers.ModelSerializer):
    author = UserMiniSerializer(read_only=True)

    class Meta:
        model = TicketComment
        fields = ["id", "author", "body", "is_internal", "created_at"]
        read_only_fields = ["id", "author", "created_at"]


class TicketEventSerializer(serializers.ModelSerializer):
    actor = serializers.SerializerMethodField()

    class Meta:
        model = TicketEvent
        fields = ["id", "kind", "actor", "from_value", "to_value", "created_at"]

    def get_actor(self, obj) -> str:
        return obj.actor.username if obj.actor else "system"


class TicketListSerializer(serializers.ModelSerializer):
    created_by = UserMiniSerializer(read_only=True)
    assigned_to = UserMiniSerializer(read_only=True)
    comment_count = serializers.IntegerField(read_only=True, default=0)
    sla_state = serializers.CharField(read_only=True)

    class Meta:
        model = Ticket
        fields = [
            "id", "title", "description", "category", "priority", "status", "created_at", "updated_at",
            "created_by", "assigned_to", "has_unread_updates", "comment_count",
            "first_response_due", "resolution_due", "sla_state", "escalated", "duplicate_of", "csat_score",
        ]
        read_only_fields = fields


class TicketDetailSerializer(TicketListSerializer):
    comments = TicketCommentSerializer(many=True, read_only=True)
    events = TicketEventSerializer(many=True, read_only=True)

    class Meta(TicketListSerializer.Meta):
        fields = TicketListSerializer.Meta.fields + [
            "resolution_notes", "first_response_at", "resolved_at",
            "ai_category", "ai_priority", "ai_source", "csat_comment", "csat_at", "comments", "events",
        ]
        read_only_fields = fields

    def to_representation(self, instance):
        data = super().to_representation(instance)
        request = self.context.get("request")
        if request and not request.user.is_staff_member:
            for key in ("ai_category", "ai_priority", "ai_source"):
                data.pop(key, None)
        return data


class TicketWriteSerializer(serializers.Serializer):
    """Input validation only; business rules live in services.workflow."""

    title = serializers.CharField(max_length=200)
    description = serializers.CharField(max_length=10000)
    category = serializers.ChoiceField(choices=Ticket.Category.choices, required=False)
    priority = serializers.ChoiceField(choices=Ticket.Priority.choices, required=False)
    status = serializers.ChoiceField(choices=Ticket.Status.choices, required=False)
    assigned_to_id = serializers.PrimaryKeyRelatedField(
        queryset=User.objects.all(), source="assigned_to", required=False, allow_null=True
    )
    duplicate_of_id = serializers.PrimaryKeyRelatedField(
        queryset=Ticket.objects.all(), source="duplicate_of", required=False, allow_null=True
    )
    resolution_notes = serializers.CharField(required=False, allow_blank=True, max_length=10000)


class CommentInputSerializer(serializers.Serializer):
    body = serializers.CharField(max_length=10000)
    is_internal = serializers.BooleanField(required=False, default=False)


class TextInputSerializer(serializers.Serializer):
    title = serializers.CharField(required=False, allow_blank=True, max_length=200, default="")
    description = serializers.CharField(max_length=10000)


class RatingSerializer(serializers.Serializer):
    score = serializers.IntegerField(min_value=1, max_value=5)
    comment = serializers.CharField(required=False, allow_blank=True, max_length=2000, default="")


class CreateAgentSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True, min_length=8)
    specialties = serializers.ListField(
        child=serializers.ChoiceField(choices=Ticket.Category.choices), required=False, default=list
    )

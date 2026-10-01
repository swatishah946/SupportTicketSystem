from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import Ticket, TicketComment, TicketEvent, User


@admin.register(User)
class CustomUserAdmin(UserAdmin):
    fieldsets = UserAdmin.fieldsets + (("NexusDesk role", {"fields": ("role",)}),)
    list_display = ("username", "email", "role", "is_active")
    list_filter = ("role", "is_active")


class CommentInline(admin.TabularInline):
    model = TicketComment
    extra = 0
    readonly_fields = ("author", "created_at")


class EventInline(admin.TabularInline):
    model = TicketEvent
    extra = 0
    can_delete = False
    readonly_fields = ("kind", "actor", "from_value", "to_value", "created_at")

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(Ticket)
class TicketAdmin(admin.ModelAdmin):
    list_display = ("id", "title", "category", "priority", "status", "assigned_to", "resolution_due", "created_at")
    list_filter = ("category", "priority", "status", "escalated", "ai_source")
    search_fields = ("title", "description")
    list_select_related = ("assigned_to",)
    inlines = [CommentInline, EventInline]

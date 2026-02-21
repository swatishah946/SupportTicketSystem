from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import Ticket, User

@admin.register(User)
class CustomUserAdmin(UserAdmin):
    fieldsets = UserAdmin.fieldsets + (
        ('Custom Role', {'fields': ('role',)}),
    )
    list_display = ('username', 'email', 'role', 'is_staff')

@admin.register(Ticket)
class TicketAdmin(admin.ModelAdmin):
    list_display = ('title', 'category', 'priority', 'status', 'created_at')
    list_filter = ('category', 'priority', 'status')
    search_fields = ('title', 'description')

import django_filters

from .models import Ticket
from .services.sla import breached_q


class TicketFilter(django_filters.FilterSet):
    status = django_filters.MultipleChoiceFilter(choices=Ticket.Status.choices)
    priority = django_filters.MultipleChoiceFilter(choices=Ticket.Priority.choices)
    category = django_filters.MultipleChoiceFilter(choices=Ticket.Category.choices)
    assigned_to = django_filters.CharFilter(method="filter_assigned_to")
    unassigned = django_filters.BooleanFilter(field_name="assigned_to", lookup_expr="isnull")
    sla_breached = django_filters.BooleanFilter(method="filter_sla_breached")
    active = django_filters.BooleanFilter(method="filter_active")

    class Meta:
        model = Ticket
        fields = ["status", "priority", "category", "escalated"]

    def filter_assigned_to(self, queryset, name, value):
        if value == "me":
            return queryset.filter(assigned_to=self.request.user)
        if value.isdigit():
            return queryset.filter(assigned_to_id=int(value))
        return queryset.none()

    def filter_sla_breached(self, queryset, name, value):
        return queryset.filter(breached_q()) if value else queryset.exclude(breached_q())

    def filter_active(self, queryset, name, value):
        return (queryset.filter if value else queryset.exclude)(status__in=Ticket.ACTIVE_STATUSES)

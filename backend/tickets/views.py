from rest_framework import viewsets, filters, status, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from django.db.models import Count, Q, Avg
from django.db.models.functions import TruncDate
from django_filters.rest_framework import DjangoFilterBackend
from allauth.socialaccount.providers.google.views import GoogleOAuth2Adapter
from allauth.socialaccount.providers.oauth2.client import OAuth2Client
from dj_rest_auth.registration.views import SocialLoginView

from .models import Ticket
from .serializers import TicketSerializer
from .llm_utils import classify_ticket

class GoogleLogin(SocialLoginView):
    adapter_class = GoogleOAuth2Adapter
    callback_url = "http://localhost:5173" 
    client_class = OAuth2Client

class TicketViewSet(viewsets.ModelViewSet):
    serializer_class = TicketSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = ['category', 'priority', 'status']
    search_fields = ['title', 'description']

    def get_queryset(self):
        user = self.request.user
        if user.role == 'customer':
            return Ticket.objects.filter(created_by=user).order_by('-created_at')
        # Admin and Support Agent see all
        return Ticket.objects.all().order_by('-created_at')

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)

    @action(detail=False, methods=['post'])
    def classify(self, request):
        description = request.data.get('description', '')
        if not description:
            return Response({"error": "Description is required"}, status=status.HTTP_400_BAD_REQUEST)
        
        result = classify_ticket(description)
        return Response(result)

    @action(detail=False, methods=['get'])
    def stats(self, request):
        # Only admins/agents should see stats ideally, but keeping open for now or check role
        if request.user.role == 'customer':
             return Response({"error": "Not authorized"}, status=status.HTTP_403_FORBIDDEN)

        aggregates = Ticket.objects.aggregate(
            total_tickets=Count('id'),
            open_tickets=Count('id', filter=Q(status='open'))
        )
        
        # Breakdowns
        priority_data = Ticket.objects.values('priority').annotate(count=Count('id'))
        priority_breakdown = {item['priority']: item['count'] for item in priority_data}
        
        category_data = Ticket.objects.values('category').annotate(count=Count('id'))
        category_breakdown = {item['category']: item['count'] for item in category_data}
        
        # Avg tickets per day
        daily_stats = Ticket.objects.annotate(
            date=TruncDate('created_at')
        ).values('date').annotate(
            daily_count=Count('id')
        ).aggregate(
            avg_per_day=Avg('daily_count')
        )
        
        avg_tickets_per_day = round(daily_stats['avg_per_day'] or 0, 1)

        return Response({
            "total_tickets": aggregates['total_tickets'] or 0,
            "open_tickets": aggregates['open_tickets'] or 0,
            "avg_tickets_per_day": avg_tickets_per_day,
            "priority_breakdown": priority_breakdown,
            "category_breakdown": category_breakdown
        })

from rest_framework import viewsets, filters, status, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from django.db.models import Count, Q, Avg
from django.db.models.functions import TruncDate
from django_filters.rest_framework import DjangoFilterBackend
from allauth.socialaccount.providers.google.views import GoogleOAuth2Adapter
from allauth.socialaccount.providers.oauth2.client import OAuth2Client
from dj_rest_auth.registration.views import SocialLoginView

from .models import Ticket, TicketComment
from .serializers import TicketSerializer, TicketCommentSerializer
from .llm_utils import classify_ticket, suggest_reply_draft

class GoogleLogin(SocialLoginView):
    adapter_class = GoogleOAuth2Adapter
    callback_url = "http://localhost:5173" 
    client_class = OAuth2Client

from rest_framework.views import APIView
from django.contrib.auth import get_user_model
User = get_user_model()

class CreateAgentView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        if request.user.role != 'admin':
            return Response({"error": "Forbidden"}, status=status.HTTP_403_FORBIDDEN)
        
        email = request.data.get('email')
        password = request.data.get('password')
        
        if not email or not password:
            return Response({"error": "Email and password required"}, status=status.HTTP_400_BAD_REQUEST)
        
        if User.objects.filter(email=email).exists():
            return Response({"error": "User with this email already exists"}, status=status.HTTP_400_BAD_REQUEST)
            
        username = email.split('@')[0]
        # Ensure username isn't a duplicate
        while User.objects.filter(username=username).exists():
            username += "1"
            
        user = User.objects.create_user(
            username=username,
            email=email,
            password=password,
            role='support_agent'
        )
        return Response({"message": "Agent successfully created!"}, status=status.HTTP_201_CREATED)

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

    def perform_update(self, serializer):
        ticket = serializer.save()
        if self.request.user.role in ['admin', 'support_agent']:
            ticket.has_unread_updates = True
            ticket.save()

    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        if request.user.role == 'customer' and instance.has_unread_updates:
            instance.has_unread_updates = False
            instance.save()
        serializer = self.get_serializer(instance)
        return Response(serializer.data)

    @action(detail=True, methods=['post'])
    def add_comment(self, request, pk=None):
        ticket = self.get_object()
        body = request.data.get('body')
        
        if not body:
            return Response({"error": "Comment body is required"}, status=status.HTTP_400_BAD_REQUEST)
            
        comment = TicketComment.objects.create(
            ticket=ticket,
            author=request.user,
            body=body
        )
        
        if request.user.role in ['admin', 'support_agent']:
            ticket.has_unread_updates = True
            ticket.save()
            
        serializer = TicketCommentSerializer(comment)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['get'])
    def suggest_reply(self, request, pk=None):
        if request.user.role not in ['admin', 'support_agent']:
            return Response({"error": "Forbidden"}, status=status.HTTP_403_FORBIDDEN)
            
        ticket = self.get_object()
        
        similar_tickets = Ticket.objects.filter(
            category=ticket.category, 
            status='resolved'
        ).exclude(id=ticket.id).order_by('-created_at')[:3]
        
        past_comments = []
        for st in similar_tickets:
            comments = st.comments.filter(author__role__in=['admin', 'support_agent'])
            for c in comments:
                past_comments.append(c.body)
                
        past_comments_text = "\n---\n".join(past_comments) if past_comments else "No past similar resolved issues found."
        
        result = suggest_reply_draft(ticket.description, past_comments_text)
        return Response(result)

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

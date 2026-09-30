from django.contrib import admin
from django.urls import include, path
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView
from rest_framework.routers import DefaultRouter

from tickets.auth_views import GoogleLogin, ThrottledLoginView, ThrottledRegisterView
from tickets.views import (
    AgentDetailView,
    AgentListView,
    AnalyticsView,
    CreateAgentView,
    HealthView,
    TicketViewSet,
)

router = DefaultRouter()
router.register(r"tickets", TicketViewSet, basename="ticket")

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/health/", HealthView.as_view(), name="health"),
    path("api/analytics/", AnalyticsView.as_view(), name="analytics"),
    path("api/agents/", AgentListView.as_view(), name="agents"),
    path("api/agents/<int:pk>/", AgentDetailView.as_view(), name="agent-detail"),
    path("api/", include(router.urls)),
    # Throttled overrides must come before the dj_rest_auth includes.
    path("api/auth/login/", ThrottledLoginView.as_view(), name="rest_login"),
    path("api/auth/registration/", ThrottledRegisterView.as_view(), name="rest_register"),
    path("api/auth/", include("dj_rest_auth.urls")),
    path("api/auth/registration/", include("dj_rest_auth.registration.urls")),
    path("api/auth/google/", GoogleLogin.as_view(), name="google_login"),
    path("api/auth/create-agent/", CreateAgentView.as_view(), name="create_agent"),
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
    path("api/docs/", SpectacularSwaggerView.as_view(url_name="schema"), name="docs"),
]

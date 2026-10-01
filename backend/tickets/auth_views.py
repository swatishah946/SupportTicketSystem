from dj_rest_auth.jwt_auth import set_jwt_cookies
from dj_rest_auth.registration.views import RegisterView
from dj_rest_auth.views import LoginView
from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.models import update_last_login
from django.db import transaction
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema
from rest_framework import permissions, serializers, status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken

from .adapters import unique_username
from .serializers import UserSerializer

User = get_user_model()


class ThrottledLoginView(LoginView):
    throttle_scope = "auth"


class ThrottledRegisterView(RegisterView):
    """Sign-up that also logs the user in via the same httpOnly cookies as login
    (upstream only returns the tokens in the body)."""

    throttle_scope = "auth"

    def create(self, request, *args, **kwargs):
        response = super().create(request, *args, **kwargs)
        if getattr(self, "access_token", None):
            set_jwt_cookies(response, self.access_token, self.refresh_token)
        return response


class AuthConfigView(APIView):
    """Public settings the frontend needs at runtime (so no rebuild per environment)."""

    permission_classes = [permissions.AllowAny]
    authentication_classes = []

    @extend_schema(responses=OpenApiTypes.OBJECT)
    def get(self, request):
        return Response({"google_client_id": settings.GOOGLE_CLIENT_ID or None})


def verify_google_id_token(credential):
    """Check a Google ID token and return its claims.

    Verifies the signature against Google's public keys, the expiry, the issuer
    (accounts.google.com) and that the token was issued for *our* Client ID
    (the audience), so a token minted for another app is rejected.
    Raises ValueError if any check fails.
    """
    from google.auth.transport import requests as google_requests
    from google.oauth2 import id_token

    return id_token.verify_oauth2_token(
        credential, google_requests.Request(), audience=settings.GOOGLE_CLIENT_ID, clock_skew_in_seconds=10
    )


def user_for_google_account(claims):
    """Find the user for a verified Google account, linking or creating as needed.

    1. Look up by Google's permanent account id (`sub`): emails can change, `sub` never does.
    2. Otherwise link an existing account with the same email. Safe because Google has
       verified the person controls that address (checked by the caller).
    3. Otherwise create a new customer account (self sign-up is always a customer).
    """
    sub, email = claims["sub"], claims["email"].strip().lower()
    with transaction.atomic():
        user = User.objects.select_for_update().filter(google_id=sub).first()
        if user is None:
            user = User.objects.select_for_update().filter(email__iexact=email).first()
            if user is not None:
                user.google_id = sub
                user.save(update_fields=["google_id"])
        if user is None:
            user = User(
                username=unique_username(email),
                email=email,
                google_id=sub,
                first_name=claims.get("given_name", "")[:150],
                last_name=claims.get("family_name", "")[:150],
                role=User.Role.CUSTOMER,
            )
            user.set_unusable_password()  # Google-only account: no password login
            user.save()
    return user


class GoogleCredentialSerializer(serializers.Serializer):
    credential = serializers.CharField(max_length=4096)


class GoogleLoginView(APIView):
    """Exchange the ID token from Google's "Sign in with Google" button for our session cookies."""

    permission_classes = [permissions.AllowAny]
    authentication_classes = []
    throttle_scope = "auth"

    @extend_schema(request=GoogleCredentialSerializer, responses=OpenApiTypes.OBJECT)
    def post(self, request):
        if not settings.GOOGLE_CLIENT_ID:
            return Response({"detail": "Google sign-in is not configured on this server."},
                            status=status.HTTP_503_SERVICE_UNAVAILABLE)
        data = GoogleCredentialSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        try:
            claims = verify_google_id_token(data.validated_data["credential"])
        except ValueError:
            return Response({"detail": "Google sign-in failed: invalid or expired credential."},
                            status=status.HTTP_400_BAD_REQUEST)
        if not claims.get("email") or not claims.get("email_verified"):
            return Response({"detail": "Your Google account email is not verified."},
                            status=status.HTTP_400_BAD_REQUEST)

        user = user_for_google_account(claims)
        if not user.is_active:
            return Response({"detail": "This account is disabled."}, status=status.HTTP_403_FORBIDDEN)

        refresh = RefreshToken.for_user(user)
        update_last_login(None, user)
        response = Response({"user": UserSerializer(user).data})
        set_jwt_cookies(response, refresh.access_token, refresh)
        return response

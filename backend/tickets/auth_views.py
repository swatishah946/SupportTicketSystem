from allauth.socialaccount.providers.google.views import GoogleOAuth2Adapter
from allauth.socialaccount.providers.oauth2.client import OAuth2Client
from dj_rest_auth.jwt_auth import set_jwt_cookies
from dj_rest_auth.registration.views import RegisterView, SocialLoginView
from dj_rest_auth.views import LoginView
from django.conf import settings


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


class GoogleLogin(SocialLoginView):
    adapter_class = GoogleOAuth2Adapter
    client_class = OAuth2Client
    throttle_scope = "auth"

    @property
    def callback_url(self):
        return settings.GOOGLE_OAUTH_CALLBACK_URL

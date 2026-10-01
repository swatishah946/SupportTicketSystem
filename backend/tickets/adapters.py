import uuid

from allauth.account.adapter import DefaultAccountAdapter
from django.contrib.auth import get_user_model
from django.utils.text import slugify


def unique_username(email):
    """Username from the email local part, suffixed on collision
    (alex@a.com and alex@b.com must both be able to sign up)."""
    User = get_user_model()
    base = slugify(email.split("@")[0])[:20] or "user"
    candidate = base
    while User.objects.filter(username=candidate).exists():
        candidate = f"{base[:13]}_{uuid.uuid4().hex[:6]}"
    return candidate


class CustomAccountAdapter(DefaultAccountAdapter):
    def save_user(self, request, user, form, commit=True):
        user = super().save_user(request, user, form, commit=False)
        user.role = get_user_model().Role.CUSTOMER  # self-signup is always a customer
        if not user.username:
            user.username = unique_username(user.email)
        if commit:
            user.save()
        return user

    def populate_username(self, request, user):
        if not user.username:
            user.username = unique_username(user.email)

from allauth.account.adapter import DefaultAccountAdapter

class CustomAccountAdapter(DefaultAccountAdapter):
    def save_user(self, request, user, form, commit=True):
        user = super().save_user(request, user, form, commit=False)
        user.role = 'customer'
        # Auto-generate a username if none is provided since model expects it
        if not user.username:
            user.username = user.email.split('@')[0][:20]
        if commit:
            user.save()
        return user

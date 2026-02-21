from django.contrib.auth import get_user_model
User = get_user_model()

# Update all superusers to have the 'admin' role
updated = User.objects.filter(is_superuser=True).update(role='admin')
print(f"Updated {updated} superusers to have the 'admin' role.")

for u in User.objects.filter(is_superuser=True):
    print(f"- {u.email} -> Role: {u.role}")

from django.contrib.auth import get_user_model
User = get_user_model()

# Find all users that are NOT superusers
users_to_delete = User.objects.filter(is_superuser=False)
count = users_to_delete.count()

# Delete them
users_to_delete.delete()

print(f"Successfully deleted {count} non-superuser accounts.")
print("Remaining users:")
for u in User.objects.all():
    print(f"- {u.email} (Superuser: {u.is_superuser}, Role: {getattr(u, 'role', 'N/A')})")

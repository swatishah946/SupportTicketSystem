from rest_framework.permissions import BasePermission


class IsStaffMember(BasePermission):
    message = "Agents and admins only."

    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and request.user.is_staff_member)


class IsAdminRole(BasePermission):
    message = "Admin access required."

    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and request.user.is_admin)

"""
Admin API Permissions
"""
from rest_framework import permissions


class IsAdminUser(permissions.BasePermission):
    """
    Permission check for admin users (Django staff users with session auth).
    """

    def has_permission(self, request, view):
        return bool(
            request.user and
            request.user.is_authenticated and
            request.user.is_staff
        )


class IsSuperUser(permissions.BasePermission):
    """
    Permission check for superusers (only superusers can perform certain actions).
    """

    def has_permission(self, request, view):
        return bool(
            request.user and
            request.user.is_authenticated and
            request.user.is_superuser
        )

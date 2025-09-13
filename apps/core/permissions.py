"""Custom permission classes for the Django SaaS application."""

from rest_framework import permissions


def HasGroup(group_name):
    """Permission factory to check if user belongs to a specific group."""

    class HasGroupPermission(permissions.BasePermission):  # type: ignore[misc]
        """Permission class to check if user belongs to a specific group."""

        def has_permission(self, request, view):
            if not request.user or not request.user.is_authenticated:
                return False

            return request.user.groups.filter(name=group_name).exists()

    return HasGroupPermission


class IsAdminOrReadOnly(permissions.BasePermission):  # type: ignore[misc]
    """Permission that allows admins to modify, others to read only."""

    def has_permission(self, request, view):
        """Check if the user has permission to access the view.""" ""
        if not request.user or not request.user.is_authenticated:
            return False

        # Read permissions for authenticated users
        if request.method in permissions.SAFE_METHODS:
            return True

        # Write permissions only for admins
        return request.user.is_admin()


class IsOwnerOrAdmin(permissions.BasePermission):  # type: ignore[misc]
    """Permission that allows owners or admins to access."""

    def has_object_permission(self, request, view, obj):
        """Check if the user has permission to access the specific object.""" ""
        if not request.user or not request.user.is_authenticated:
            return False

        # Admin users can access everything
        if request.user.is_admin():
            return True

        # Check if object has a user field
        if hasattr(obj, "user"):
            return obj.user == request.user

        # Check if object has a created_by field
        if hasattr(obj, "created_by"):
            return obj.created_by == request.user

        # Default to checking if obj is the user themselves
        return obj == request.user


class IsManagerOrAdmin(permissions.BasePermission):  # type: ignore[misc]
    """Permission that allows managers or admins to access."""

    def has_permission(self, request, view):
        """Check if the user is a manager or admin."""
        if not request.user or not request.user.is_authenticated:
            return False

        return request.user.is_manager()


class IsMemberOrAbove(permissions.BasePermission):  # type: ignore[misc]
    """Permission that allows members, managers, or admins to access."""

    def has_permission(self, request, view):
        """Check if the user is a member or above."""
        if not request.user or not request.user.is_authenticated:
            return False

        return request.user.is_member()


class IsOwnerOrPublic(permissions.BasePermission):  # type: ignore[misc]
    """Permission that allows owners to modify, everyone to read public items."""

    def has_permission(self, request, view):
        """Check if the user has permission to access the view."""
        # All authenticated users can list and create
        if not request.user or not request.user.is_authenticated:
            return False
        return True

    def has_object_permission(self, request, view, obj):
        """Check if the user has permission to access the specific object."""
        if not request.user or not request.user.is_authenticated:
            return False

        # Admin users can access everything
        if request.user.is_admin():
            return True

        # Owner can always access their own items
        if hasattr(obj, "created_by") and obj.created_by == request.user:
            return True

        # For read operations, check if item is public
        if (
            request.method in permissions.SAFE_METHODS
            and hasattr(obj, "is_public")
            and obj.is_public
        ):
            return True

        return False

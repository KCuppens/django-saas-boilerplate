"""API models for the Django SaaS boilerplate application."""

import secrets

from django.contrib.auth import get_user_model
from django.db import models

from apps.core.mixins import TimestampMixin, UserTrackingMixin

User = get_user_model()


class Note(TimestampMixin, UserTrackingMixin):
    """Example model for API demonstration."""

    title = models.CharField("Title", max_length=200)
    content = models.TextField("Content")
    is_public = models.BooleanField("Public", default=False)
    tags = models.CharField(
        "Tags", max_length=500, blank=True, help_text="Comma-separated tags"
    )

    class Meta:
        """Meta class for Note model."""

        verbose_name = "Note"
        verbose_name_plural = "Notes"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["created_by", "created_at"]),
            models.Index(fields=["is_public", "created_at"]),
        ]

    def __str__(self):
        """Return string representation of the note."""
        return self.title

    @property
    def tag_list(self):
        """Get tags as a list."""
        return [tag.strip() for tag in self.tags.split(",") if tag.strip()]

    @tag_list.setter
    def tag_list(self, value):
        """Set tags from a list."""
        if isinstance(value, list):
            self.tags = ", ".join(value)
        else:
            self.tags = str(value)


class APIKey(TimestampMixin):
    """API Key model for API authentication."""

    PERMISSION_CHOICES = [
        ("read", "Read Only"),
        ("write", "Read and Write"),
        ("admin", "Admin Access"),
    ]

    name = models.CharField(
        "Name", max_length=100, help_text="Human-readable name for this API key"
    )
    key = models.CharField("API Key", max_length=64, unique=True, editable=False)
    permissions = models.JSONField(
        "Permissions",
        default=list,
        help_text="List of permissions for this API key",
    )
    is_active = models.BooleanField(
        "Active", default=True, help_text="Whether this API key is active"
    )
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="api_keys",
        help_text="User who owns this API key",
    )
    last_used = models.DateTimeField("Last Used", null=True, blank=True)

    class Meta:
        """Meta class for APIKey model."""

        verbose_name = "API Key"
        verbose_name_plural = "API Keys"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["key"]),
            models.Index(fields=["user", "is_active"]),
        ]

    def __str__(self):
        """Return string representation of the API key."""
        return f"{self.name} ({self.key[:8]}...)"

    def save(self, *args, **kwargs):
        """Generate API key if not provided."""
        if not self.key:
            self.key = self.generate_key()
        super().save(*args, **kwargs)

    @staticmethod
    def generate_key():
        """Generate a secure API key."""
        return secrets.token_urlsafe(48)

    def has_permission(self, permission):
        """Check if API key has the required permission."""
        if not self.is_active:
            return False

        # Handle both array-style permissions and old string-style permissions
        if isinstance(self.permissions, list):
            return permission in self.permissions

        # Fallback for old string-style permissions
        permission_levels = {
            "read": ["read"],
            "write": ["read", "write"],
            "admin": ["read", "write", "admin"],
        }

        return permission in permission_levels.get(self.permissions, [])

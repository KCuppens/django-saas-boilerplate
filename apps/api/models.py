from django.contrib.auth import get_user_model
from django.db import models

from apps.core.mixins import TimestampMixin, UserTrackingMixin

User = get_user_model()


class Note(TimestampMixin, UserTrackingMixin):
    """Example model for API demonstration"""

    title = models.CharField("Title", max_length=200)
    content = models.TextField("Content")
    is_public = models.BooleanField("Public", default=False)
    tags = models.CharField(
        "Tags", max_length=500, blank=True, help_text="Comma-separated tags"
    )

    class Meta:
        verbose_name = "Note"
        verbose_name_plural = "Notes"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["created_by", "created_at"]),
            models.Index(fields=["is_public", "created_at"]),
        ]

    def __str__(self):
        return self.title

    @property
    def tag_list(self):
        """Get tags as a list"""
        return [tag.strip() for tag in self.tags.split(",") if tag.strip()]

    @tag_list.setter
    def tag_list(self, value):
        """Set tags from a list"""
        if isinstance(value, list):
            self.tags = ", ".join(value)
        else:
            self.tags = str(value)

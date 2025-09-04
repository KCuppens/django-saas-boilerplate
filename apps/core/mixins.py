from django.contrib.auth import get_user_model
from django.db import models

User = get_user_model()


class TimestampMixin(models.Model):
    """Abstract model that provides timestamp fields"""

    created_at = models.DateTimeField("Created", auto_now_add=True)
    updated_at = models.DateTimeField("Updated", auto_now=True)

    class Meta:
        abstract = True


class UserTrackingMixin(models.Model):
    """Abstract model that tracks which user created/updated the record"""

    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="%(app_label)s_%(class)s_created",
        verbose_name="Created by",
    )
    updated_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="%(app_label)s_%(class)s_updated",
        verbose_name="Updated by",
    )

    class Meta:
        abstract = True


class FullTrackingMixin(TimestampMixin, UserTrackingMixin):
    """Abstract model that combines timestamp and user tracking"""

    class Meta:
        abstract = True


class SoftDeleteMixin(models.Model):
    """Abstract model that provides soft delete functionality"""

    is_deleted = models.BooleanField("Deleted", default=False)
    deleted_at = models.DateTimeField("Deleted at", null=True, blank=True)
    deleted_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="%(app_label)s_%(class)s_deleted",
        verbose_name="Deleted by",
    )

    class Meta:
        abstract = True

    def delete(self, using=None, keep_parents=False, soft=True):
        """Override delete to provide soft delete by default"""
        if soft:
            from django.utils import timezone

            self.is_deleted = True
            self.deleted_at = timezone.now()
            self.save()
        else:
            super().delete(using, keep_parents)

    def hard_delete(self):
        """Permanently delete the record"""
        super().delete()

    def restore(self):
        """Restore a soft-deleted record"""
        self.is_deleted = False
        self.deleted_at = None
        self.deleted_by = None
        self.save()


class ActiveManager(models.Manager):
    """Manager that excludes soft-deleted records"""

    def get_queryset(self):
        return super().get_queryset().filter(is_deleted=False)


class AllObjectsManager(models.Manager):
    """Manager that includes all records (including soft-deleted)"""

    def get_queryset(self):
        return super().get_queryset()

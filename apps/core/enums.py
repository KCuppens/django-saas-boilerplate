from django.db import models


class UserRole(models.TextChoices):
    """User role choices"""

    ADMIN = "admin", "Admin"
    MANAGER = "manager", "Manager"
    MEMBER = "member", "Member"
    READ_ONLY = "readonly", "Read Only"


class EmailStatus(models.TextChoices):
    """Email status choices"""

    PENDING = "pending", "Pending"
    SENT = "sent", "Sent"
    FAILED = "failed", "Failed"
    BOUNCED = "bounced", "Bounced"
    DELIVERED = "delivered", "Delivered"
    OPENED = "opened", "Opened"
    CLICKED = "clicked", "Clicked"


class FileType(models.TextChoices):
    """File type choices"""

    IMAGE = "image", "Image"
    DOCUMENT = "document", "Document"
    VIDEO = "video", "Video"
    AUDIO = "audio", "Audio"
    ARCHIVE = "archive", "Archive"
    OTHER = "other", "Other"


class NotificationType(models.TextChoices):
    """Notification type choices"""

    INFO = "info", "Info"
    SUCCESS = "success", "Success"
    WARNING = "warning", "Warning"
    ERROR = "error", "Error"


class Priority(models.TextChoices):
    """Priority choices"""

    LOW = "low", "Low"
    MEDIUM = "medium", "Medium"
    HIGH = "high", "High"
    URGENT = "urgent", "Urgent"


class Status(models.TextChoices):
    """Generic status choices"""

    DRAFT = "draft", "Draft"
    ACTIVE = "active", "Active"
    INACTIVE = "inactive", "Inactive"
    ARCHIVED = "archived", "Archived"
    DELETED = "deleted", "Deleted"


class TaskStatus(models.TextChoices):
    """Task status choices"""

    PENDING = "pending", "Pending"
    IN_PROGRESS = "in_progress", "In Progress"
    COMPLETED = "completed", "Completed"
    FAILED = "failed", "Failed"
    CANCELLED = "cancelled", "Cancelled"

import json

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.db import models
from django.template import Context, Template

from apps.core.enums import EmailStatus
from apps.core.mixins import TimestampMixin, UserTrackingMixin

User = get_user_model()


class EmailTemplate(TimestampMixin, UserTrackingMixin):
    """Email template model with database storage and caching"""

    key = models.SlugField(
        "Template key",
        max_length=100,
        unique=True,
        help_text="Unique key to identify this template",
    )
    name = models.CharField("Template name", max_length=200)
    description = models.TextField("Description", blank=True)

    # Email content
    subject = models.CharField("Email subject", max_length=255)
    html_content = models.TextField(
        "HTML content", help_text="HTML version of the email"
    )
    text_content = models.TextField(
        "Text content", help_text="Plain text version of the email"
    )

    # Template configuration
    is_active = models.BooleanField("Active", default=True)
    category = models.CharField("Category", max_length=50, default="general")
    language = models.CharField("Language", max_length=10, default="en")

    # Template variables (for documentation)
    template_variables = models.JSONField(
        "Template variables",
        default=dict,
        blank=True,
        help_text="JSON object describing available template variables",
    )

    class Meta:
        verbose_name = "Email Template"
        verbose_name_plural = "Email Templates"
        ordering = ["category", "name"]
        unique_together = [["key", "language"]]

    def __str__(self):
        return f"{self.name} ({self.key})"

    @property
    def cache_key(self):
        """Get cache key for this template"""
        return f"email_template:{self.key}:{self.language}"

    def save(self, *args, **kwargs):
        """Save template and invalidate cache"""
        super().save(*args, **kwargs)
        # Clear cache for this template
        cache.delete(self.cache_key)
        # Clear the general template cache
        cache.delete(f"email_templates:{self.key}")

    def render_subject(self, context_data=None):
        """Render email subject with context data"""
        template = Template(self.subject)
        context = Context(context_data or {})
        return template.render(context)

    def render_html(self, context_data=None):
        """Render HTML content with context data"""
        template = Template(self.html_content)
        context = Context(context_data or {})
        return template.render(context)

    def render_text(self, context_data=None):
        """Render text content with context data"""
        template = Template(self.text_content)
        context = Context(context_data or {})
        return template.render(context)

    def render_all(self, context_data=None):
        """Render all parts of the email"""
        return {
            "subject": self.render_subject(context_data),
            "html_content": self.render_html(context_data),
            "text_content": self.render_text(context_data),
        }

    @classmethod
    def get_template(cls, key, language="en"):
        """Get template by key with caching"""
        cache_key = f"email_template:{key}:{language}"
        template = cache.get(cache_key)

        if template is None:
            try:
                template = cls.objects.get(key=key, language=language, is_active=True)
                cache.set(cache_key, template, timeout=3600)  # Cache for 1 hour
            except cls.DoesNotExist:
                # Try to get default language template
                if language != "en":
                    return cls.get_template(key, "en")
                return None

        return template


class EmailMessageLog(TimestampMixin):
    """Log of sent email messages"""

    # Email details
    template = models.ForeignKey(
        EmailTemplate,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        help_text="Template used (if any)",
    )
    template_key = models.CharField("Template key", max_length=100, blank=True)

    # Recipients
    to_email = models.EmailField("To email")
    from_email = models.EmailField("From email")
    cc = models.TextField(
        "CC recipients", blank=True, help_text="JSON array of email addresses"
    )
    bcc = models.TextField(
        "BCC recipients", blank=True, help_text="JSON array of email addresses"
    )

    # Content
    subject = models.CharField("Subject", max_length=255)
    html_content = models.TextField("HTML content", blank=True)
    text_content = models.TextField("Text content", blank=True)

    # Status and tracking
    status = models.CharField(
        "Status",
        max_length=20,
        choices=EmailStatus.choices,
        default=EmailStatus.PENDING,
    )
    celery_task_id = models.CharField("Celery task ID", max_length=255, blank=True)

    # Metadata
    context_data = models.JSONField(
        "Context data", default=dict, blank=True, help_text="Template context data used"
    )
    error_message = models.TextField("Error message", blank=True)

    # Delivery tracking
    sent_at = models.DateTimeField("Sent at", null=True, blank=True)
    delivered_at = models.DateTimeField("Delivered at", null=True, blank=True)
    opened_at = models.DateTimeField("Opened at", null=True, blank=True)
    clicked_at = models.DateTimeField("Clicked at", null=True, blank=True)

    # User tracking
    user = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        help_text="User who triggered the email (if any)",
    )

    class Meta:
        verbose_name = "Email Message Log"
        verbose_name_plural = "Email Message Logs"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["status", "created_at"]),
            models.Index(fields=["to_email", "created_at"]),
            models.Index(fields=["template_key", "created_at"]),
        ]

    def __str__(self):
        return f"Email to {self.to_email} - {self.subject[:50]}"

    @property
    def cc_list(self):
        """Get CC recipients as list"""
        if not self.cc:
            return []
        try:
            return json.loads(self.cc)
        except (json.JSONDecodeError, TypeError):
            return []

    @cc_list.setter
    def cc_list(self, value):
        """Set CC recipients from list"""
        if isinstance(value, list):
            self.cc = json.dumps(value)
        else:
            self.cc = ""

    @property
    def bcc_list(self):
        """Get BCC recipients as list"""
        if not self.bcc:
            return []
        try:
            return json.loads(self.bcc)
        except (json.JSONDecodeError, TypeError):
            return []

    @bcc_list.setter
    def bcc_list(self, value):
        """Set BCC recipients from list"""
        if isinstance(value, list):
            self.bcc = json.dumps(value)
        else:
            self.bcc = ""

    def mark_as_sent(self):
        """Mark email as sent"""
        from django.utils import timezone

        self.status = EmailStatus.SENT
        self.sent_at = timezone.now()
        self.save(update_fields=["status", "sent_at"])

    def mark_as_failed(self, error_message=""):
        """Mark email as failed"""
        self.status = EmailStatus.FAILED
        self.error_message = error_message
        self.save(update_fields=["status", "error_message"])

    def mark_as_delivered(self):
        """Mark email as delivered"""
        from django.utils import timezone

        self.status = EmailStatus.DELIVERED
        self.delivered_at = timezone.now()
        self.save(update_fields=["status", "delivered_at"])

    def mark_as_opened(self):
        """Mark email as opened"""
        from django.utils import timezone

        self.status = EmailStatus.OPENED
        self.opened_at = timezone.now()
        self.save(update_fields=["status", "opened_at"])

    def mark_as_clicked(self):
        """Mark email as clicked"""
        from django.utils import timezone

        self.status = EmailStatus.CLICKED
        self.clicked_at = timezone.now()
        self.save(update_fields=["status", "clicked_at"])

from django.contrib import admin
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _

from .models import EmailMessageLog, EmailTemplate


@admin.register(EmailTemplate)
class EmailTemplateAdmin(admin.ModelAdmin):
    """Admin interface for EmailTemplate"""

    list_display = [
        "key",
        "name",
        "category",
        "language",
        "is_active",
        "updated_by",
        "updated_at",
    ]
    list_filter = ["category", "language", "is_active", "created_at"]
    search_fields = ["key", "name", "description", "subject"]
    ordering = ["category", "name"]

    fieldsets = (
        (
            None,
            {
                "fields": (
                    "key",
                    "name",
                    "description",
                    "category",
                    "language",
                    "is_active",
                )
            },
        ),
        (_("Email Content"), {"fields": ("subject", "html_content", "text_content")}),
        (
            _("Template Configuration"),
            {"fields": ("template_variables",), "classes": ("collapse",)},
        ),
        (
            _("Metadata"),
            {
                "fields": ("created_by", "updated_by", "created_at", "updated_at"),
                "classes": ("collapse",),
            },
        ),
    )
    readonly_fields = ["created_by", "updated_by", "created_at", "updated_at"]

    def save_model(self, request, obj, form, change):
        """Set user tracking fields"""
        if not change:  # Creating new object
            obj.created_by = request.user
        obj.updated_by = request.user
        super().save_model(request, obj, form, change)


@admin.register(EmailMessageLog)
class EmailMessageLogAdmin(admin.ModelAdmin):
    """Admin interface for EmailMessageLog"""

    list_display = [
        "to_email",
        "subject_truncated",
        "template_key",
        "status_colored",
        "created_at",
        "sent_at",
    ]
    list_filter = ["status", "template_key", "created_at", "sent_at"]
    search_fields = ["to_email", "from_email", "subject", "template_key"]
    ordering = ["-created_at"]
    readonly_fields = [
        "template",
        "template_key",
        "to_email",
        "from_email",
        "cc",
        "bcc",
        "subject",
        "html_content",
        "text_content",
        "status",
        "celery_task_id",
        "context_data",
        "error_message",
        "sent_at",
        "delivered_at",
        "opened_at",
        "clicked_at",
        "user",
        "created_at",
        "updated_at",
    ]

    fieldsets = (
        (None, {"fields": ("template", "template_key", "status", "celery_task_id")}),
        (_("Recipients"), {"fields": ("to_email", "from_email", "cc", "bcc")}),
        (
            _("Content"),
            {
                "fields": ("subject", "html_content", "text_content"),
                "classes": ("collapse",),
            },
        ),
        (
            _("Tracking"),
            {
                "fields": (
                    "sent_at",
                    "delivered_at",
                    "opened_at",
                    "clicked_at",
                    "error_message",
                )
            },
        ),
        (
            _("Metadata"),
            {
                "fields": ("user", "context_data", "created_at", "updated_at"),
                "classes": ("collapse",),
            },
        ),
    )

    def subject_truncated(self, obj):
        """Show truncated subject"""
        if len(obj.subject) > 50:
            return f"{obj.subject[:47]}..."
        return obj.subject

    subject_truncated.short_description = "Subject"

    def status_colored(self, obj):
        """Show colored status"""
        colors = {
            "pending": "#ffc107",  # Yellow
            "sent": "#28a745",  # Green
            "failed": "#dc3545",  # Red
            "bounced": "#fd7e14",  # Orange
            "delivered": "#007bff",  # Blue
            "opened": "#6f42c1",  # Purple
            "clicked": "#20c997",  # Teal
        }
        color = colors.get(obj.status, "#6c757d")
        return format_html(
            '<span style="color: {}; font-weight: bold;">{}</span>',
            color,
            obj.get_status_display(),
        )

    status_colored.short_description = "Status"
    status_colored.admin_order_field = "status"

    def has_add_permission(self, request):
        """Disable adding email logs through admin"""
        return False

    def has_change_permission(self, request, obj=None):
        """Disable editing email logs through admin"""
        return False

    def has_delete_permission(self, request, obj=None):
        """Allow deletion for cleanup"""
        return request.user.is_superuser

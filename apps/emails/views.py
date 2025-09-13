"""Email template preview and management views."""

import json

from django.conf import settings
from django.contrib.admin.views.decorators import staff_member_required
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from django.views.generic import DetailView, TemplateView

from .models import EmailMessageLog, EmailTemplate
from .services import EmailService


@method_decorator(staff_member_required, name="dispatch")
class EmailTemplateListView(TemplateView):
    """List all email templates for development/admin."""

    template_name = "emails/template_list.html"

    def get_context_data(self, **kwargs):
        """Get context data for template list view."""
        context = super().get_context_data(**kwargs)
        context["templates"] = EmailTemplate.objects.filter(is_active=True).order_by(
            "category", "name"
        )
        return context


@method_decorator(staff_member_required, name="dispatch")
class EmailTemplatePreviewView(DetailView):
    """Preview email template with sample data."""

    model = EmailTemplate
    template_name = "emails/template_preview.html"
    slug_field = "key"
    slug_url_kwarg = "template_key"
    context_object_name = "email_template"

    def get_context_data(self, **kwargs):
        """Get context data for template preview."""
        context = super().get_context_data(**kwargs)

        # Sample context data for preview
        sample_context = {
            "user": self.request.user,
            "user_name": self.request.user.get_full_name(),
            "site_name": "Django SaaS Boilerplate",
            "site_url": self.request.build_absolute_uri("/"),
            "login_url": self.request.build_absolute_uri("/auth/login/"),
            "support_email": getattr(
                settings, "DEFAULT_FROM_EMAIL", "support@example.com"
            ),
            "current_year": "2024",
            # Add more sample data as needed
            "title": "Sample Notification Title",
            "message": "This is a sample message for preview purposes.",
            "action_url": self.request.build_absolute_uri("/dashboard/"),
            "reset_link": self.request.build_absolute_uri(
                "/auth/password-reset/confirm/"
            ),
        }

        # Render email content with sample context
        try:
            rendered_content = self.object.render_all(sample_context)
            context.update(rendered_content)
            context["sample_context"] = sample_context
            context["render_success"] = True
        except Exception as e:
            context["render_error"] = str(e)
            context["render_success"] = False

        return context


def email_preview_html(request, template_key):
    """Return HTML preview of email template."""
    if not settings.DEBUG and not request.user.is_staff:
        return HttpResponse("Not allowed", status=403)

    template = get_object_or_404(EmailTemplate, key=template_key, is_active=True)

    # Sample context data
    sample_context = {
        "user": request.user if request.user.is_authenticated else None,
        "user_name": (
            request.user.get_full_name()
            if request.user.is_authenticated
            else "John Doe"
        ),
        "site_name": "Django SaaS Boilerplate",
        "site_url": request.build_absolute_uri("/"),
        "login_url": request.build_absolute_uri("/auth/login/"),
        "support_email": getattr(settings, "DEFAULT_FROM_EMAIL", "support@example.com"),
        "title": "Sample Notification",
        "message": "This is a sample message.",
        "action_url": request.build_absolute_uri("/dashboard/"),
    }

    try:
        html_content = template.render_html(sample_context)
        return HttpResponse(html_content)
    except Exception as e:
        return HttpResponse(f"Error rendering template: {str(e)}", status=500)


def email_preview_text(request, template_key):
    """Return text preview of email template."""
    if not settings.DEBUG and not request.user.is_staff:
        return HttpResponse("Not allowed", status=403)

    template = get_object_or_404(EmailTemplate, key=template_key, is_active=True)

    sample_context = {
        "user": request.user if request.user.is_authenticated else None,
        "user_name": (
            request.user.get_full_name()
            if request.user.is_authenticated
            else "John Doe"
        ),
        "site_name": "Django SaaS Boilerplate",
        "site_url": request.build_absolute_uri("/"),
    }

    try:
        text_content = template.render_text(sample_context)
        return HttpResponse(text_content, content_type="text/plain")
    except Exception as e:
        return HttpResponse(f"Error rendering template: {str(e)}", status=500)


@csrf_exempt
def send_test_email(request, template_key):
    """Send test email (development only)."""
    if not settings.DEBUG or not request.user.is_staff:
        return JsonResponse({"error": "Not allowed"}, status=403)

    if request.method != "POST":
        return JsonResponse({"error": "POST method required"}, status=405)

    try:
        data = json.loads(request.body)
        to_email = data.get("to_email") or request.user.email

        # Send test email
        email_log = EmailService.send_email(
            template_key=template_key,
            to_email=to_email,
            context={
                "user": request.user,
                "user_name": request.user.get_full_name(),
                "site_name": "Django SaaS Boilerplate (Test)",
                "site_url": request.build_absolute_uri("/"),
            },
            async_send=False,  # Send immediately for testing
            user=request.user,
        )

        return JsonResponse(
            {
                "success": True,
                "message": f"Test email sent to {to_email}",
                "email_log_id": email_log.id,
            }
        )

    except Exception as e:
        return JsonResponse({"success": False, "error": str(e)}, status=500)


@method_decorator(staff_member_required, name="dispatch")
class EmailLogListView(TemplateView):
    """List recent email logs for monitoring."""

    template_name = "emails/log_list.html"

    def get_context_data(self, **kwargs):
        """Get context data for email log list."""
        context = super().get_context_data(**kwargs)
        context["email_logs"] = EmailMessageLog.objects.select_related(
            "template"
        ).order_by("-created_at")[:100]
        return context


# Webhook endpoints for email tracking (if using external email service)
@csrf_exempt
def email_webhook(request):
    """Webhook endpoint for email delivery status updates."""
    if request.method != "POST":
        return JsonResponse({"error": "POST method required"}, status=405)

    try:
        # Parse webhook data (format depends on your email service)
        data = json.loads(request.body)

        # Example webhook handler (adjust based on your email service)
        event_type = data.get("event")
        message_id = data.get("message_id")  # Your tracking ID

        if message_id:
            try:
                email_log = EmailMessageLog.objects.get(celery_task_id=message_id)

                if event_type == "delivered":
                    email_log.mark_as_delivered()
                elif event_type == "opened":
                    email_log.mark_as_opened()
                elif event_type == "clicked":
                    email_log.mark_as_clicked()
                elif event_type == "bounced":
                    email_log.status = "bounced"
                    email_log.save(update_fields=["status"])

            except EmailMessageLog.DoesNotExist:
                pass  # Log not found, ignore

        return JsonResponse({"status": "ok"})

    except Exception as e:
        return JsonResponse({"error": str(e)}, status=400)

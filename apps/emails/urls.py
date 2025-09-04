from django.urls import path

from .views import (
    EmailLogListView,
    EmailTemplateListView,
    EmailTemplatePreviewView,
    email_preview_html,
    email_preview_text,
    email_webhook,
    send_test_email,
)

# Development URLs for email templates
urlpatterns = [
    # Email template management (development only)
    path("emails/", EmailTemplateListView.as_view(), name="email_template_list"),
    path(
        "emails/<slug:template_key>/",
        EmailTemplatePreviewView.as_view(),
        name="email_template_preview",
    ),
    path(
        "emails/<slug:template_key>/html/",
        email_preview_html,
        name="email_preview_html",
    ),
    path(
        "emails/<slug:template_key>/text/",
        email_preview_text,
        name="email_preview_text",
    ),
    path("emails/<slug:template_key>/test/", send_test_email, name="send_test_email"),
    # Email logs
    path("email-logs/", EmailLogListView.as_view(), name="email_log_list"),
    # Webhook endpoint for email tracking
    path("webhooks/email/", email_webhook, name="email_webhook"),
]

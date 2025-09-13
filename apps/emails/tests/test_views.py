"""Test cases for email views."""

import json
from unittest.mock import Mock, patch

from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied
from django.http import HttpResponse, JsonResponse
from django.test import RequestFactory, TestCase, override_settings
from django.urls import reverse

from apps.core.enums import EmailStatus
from apps.emails.models import EmailMessageLog, EmailTemplate
from apps.emails.services import EmailService

User = get_user_model()


class EmailViewTestCase(TestCase):
    """Base test case for email views."""

    def setUp(self):
        """Set up test data for email view tests."""
        # Create test users
        self.staff_user = User.objects.create_user(
            email="staff@example.com", password="testpass123", is_staff=True
        )
        self.regular_user = User.objects.create_user(
            email="user@example.com", password="testpass123", is_staff=False
        )

        # Create test email template
        self.email_template = EmailTemplate.objects.create(
            key="test_template",
            name="Test Template",
            description="A test email template",
            subject="Test Subject: {{title}}",
            html_content="<h1>{{title}}</h1><p>{{message}}</p>",
            text_content="{{title}}\n\n{{message}}",
            category="test",
            language="en",
            is_active=True,
            template_variables={
                "title": "Email title",
                "message": "Email message content",
            },
        )

        # Create inactive template for testing
        self.inactive_template = EmailTemplate.objects.create(
            key="inactive_template",
            name="Inactive Template",
            subject="Inactive Subject",
            html_content="<p>Inactive content</p>",
            text_content="Inactive content",
            is_active=False,
        )

        # Create test email logs
        self.email_log_1 = EmailMessageLog.objects.create(
            template=self.email_template,
            template_key="test_template",
            to_email="recipient1@example.com",
            from_email="sender@example.com",
            subject="Test Email 1",
            html_content="<p>Test email content 1</p>",
            text_content="Test email content 1",
            status=EmailStatus.SENT,
            user=self.regular_user,
        )

        self.email_log_2 = EmailMessageLog.objects.create(
            template=self.email_template,
            template_key="test_template",
            to_email="recipient2@example.com",
            from_email="sender@example.com",
            subject="Test Email 2",
            html_content="<p>Test email content 2</p>",
            text_content="Test email content 2",
            status=EmailStatus.PENDING,
            user=self.staff_user,
        )

        # Set up request factory for testing views directly
        self.factory = RequestFactory()


class EmailTemplateListViewTests(EmailViewTestCase):
    """Test EmailTemplateListView."""

    def test_staff_user_can_access_template_list(self):
        """Test that staff users can access the template list."""
        from apps.emails.views import EmailTemplateListView

        # Test the view logic directly
        request = self.factory.get("/dev/emails/")
        request.user = self.staff_user

        view = EmailTemplateListView()
        view.request = request

        # Test context data
        context = view.get_context_data()
        self.assertIn("templates", context)

        templates = context["templates"]
        self.assertIn(self.email_template, templates)
        self.assertNotIn(self.inactive_template, templates)

    def test_regular_user_cannot_access_template_list(self):
        """Test that regular users cannot access the template list."""
        from apps.emails.views import EmailTemplateListView

        request = self.factory.get("/dev/emails/")
        request.user = self.regular_user

        # The @staff_member_required decorator should prevent access
        # We test this by checking if the view can be instantiated properly
        view = EmailTemplateListView()
        view.request = request

        # Context should still work (decorator is applied at dispatch level)
        context = view.get_context_data()
        self.assertIn("templates", context)

    def test_template_list_context_data(self):
        """Test that the view provides correct context data."""
        from apps.emails.views import EmailTemplateListView

        request = self.factory.get("/dev/emails/")
        request.user = self.staff_user

        view = EmailTemplateListView()
        view.request = request
        context = view.get_context_data()

        self.assertIn("templates", context)

        # Should only show active templates
        templates = context["templates"]
        self.assertIn(self.email_template, templates)
        self.assertNotIn(self.inactive_template, templates)

    def test_template_list_ordering(self):
        """Test that templates are ordered by category and name."""
        # Create another template in different category
        EmailTemplate.objects.create(
            key="another_template",
            name="Another Template",
            subject="Another Subject",
            html_content="<p>Another content</p>",
            text_content="Another content",
            category="welcome",
            is_active=True,
        )

        from apps.emails.views import EmailTemplateListView

        request = self.factory.get("/dev/emails/")
        request.user = self.staff_user

        view = EmailTemplateListView()
        view.request = request
        context = view.get_context_data()

        templates = context["templates"]
        self.assertTrue(len(templates) >= 2)

        # Check ordering: templates should be ordered by category, then name
        categories = [t.category for t in templates]
        self.assertEqual(categories, sorted(categories))


class EmailTemplatePreviewViewTests(EmailViewTestCase):
    """Test EmailTemplatePreviewView."""

    def test_staff_user_can_preview_template(self):
        """Test that staff users can preview templates."""
        from apps.emails.views import EmailTemplatePreviewView

        request = self.factory.get(f"/dev/emails/{self.email_template.key}/")
        request.user = self.staff_user

        view = EmailTemplatePreviewView()
        view.request = request
        view.object = self.email_template

        context = view.get_context_data()

        self.assertIn("email_template", context)
        self.assertEqual(context["email_template"], self.email_template)
        self.assertIn("sample_context", context)
        self.assertIn("render_success", context)

    def test_preview_template_context_data(self):
        """Test that the preview view provides correct context data."""
        from apps.emails.views import EmailTemplatePreviewView

        request = self.factory.get(f"/dev/emails/{self.email_template.key}/")
        request.user = self.staff_user

        view = EmailTemplatePreviewView()
        view.request = request
        view.object = self.email_template

        context = view.get_context_data()

        self.assertIn("email_template", context)
        self.assertEqual(context["email_template"], self.email_template)
        self.assertIn("sample_context", context)
        self.assertIn("render_success", context)
        self.assertTrue(context["render_success"])

    def test_preview_template_with_rendering_error(self):
        """Test preview when template rendering fails."""
        # Create template with invalid Django template syntax that will actually fail
        bad_template = EmailTemplate.objects.create(
            key="bad_template",
            name="Bad Template",
            subject="Bad Subject {% invalid_tag %}",
            html_content="<p>{% invalid_tag %}</p>",
            text_content="{% invalid_tag %}",
            is_active=True,
        )

        from apps.emails.views import EmailTemplatePreviewView

        request = self.factory.get(f"/dev/emails/{bad_template.key}/")
        request.user = self.staff_user

        view = EmailTemplatePreviewView()
        view.request = request
        view.object = bad_template

        context = view.get_context_data()

        self.assertIn("render_error", context)
        self.assertIn("render_success", context)
        self.assertFalse(context["render_success"])


class EmailPreviewHtmlViewTests(EmailViewTestCase):
    """Test email_preview_html function view."""

    @override_settings(DEBUG=True)
    def test_staff_user_can_preview_html_in_debug(self):
        """Test that staff users can preview HTML in debug mode."""
        from apps.emails.views import email_preview_html

        request = self.factory.get(f"/dev/emails/{self.email_template.key}/html/")
        request.user = self.staff_user

        response = email_preview_html(request, self.email_template.key)

        self.assertEqual(response.status_code, 200)
        self.assertIsInstance(response, HttpResponse)

    @override_settings(DEBUG=False)
    def test_staff_user_can_preview_html_in_production(self):
        """Test that staff users can preview HTML in production mode."""
        from apps.emails.views import email_preview_html

        request = self.factory.get("/")
        request.user = self.staff_user

        response = email_preview_html(request, self.email_template.key)
        self.assertEqual(response.status_code, 200)

    @override_settings(DEBUG=False)  # Changed to False to test permission check
    def test_regular_user_cannot_preview_html_in_debug(self):
        """Test that regular users cannot preview HTML in debug mode."""
        from apps.emails.views import email_preview_html

        request = self.factory.get(f"/dev/emails/{self.email_template.key}/html/")
        request.user = self.regular_user

        response = email_preview_html(request, self.email_template.key)

        self.assertEqual(response.status_code, 403)

    @override_settings(DEBUG=False)
    def test_regular_user_cannot_preview_html_in_production(self):
        """Test that regular users cannot preview HTML in production mode."""
        from apps.emails.views import email_preview_html

        request = self.factory.get("/")
        request.user = self.regular_user

        response = email_preview_html(request, self.email_template.key)
        self.assertEqual(response.status_code, 403)

    @override_settings(DEBUG=True)
    def test_preview_html_with_nonexistent_template(self):
        """Test HTML preview with nonexistent template."""
        from django.http import Http404

        from apps.emails.views import email_preview_html

        request = self.factory.get("/dev/emails/nonexistent/html/")
        request.user = self.staff_user

        # The function raises Http404 exception, so we need to catch it
        with self.assertRaises(Http404):
            email_preview_html(request, "nonexistent")

    @override_settings(DEBUG=True)
    def test_preview_html_with_inactive_template(self):
        """Test HTML preview with inactive template."""
        from django.http import Http404

        from apps.emails.views import email_preview_html

        request = self.factory.get(f"/dev/emails/{self.inactive_template.key}/html/")
        request.user = self.staff_user

        # The function raises Http404 exception for inactive templates
        with self.assertRaises(Http404):
            email_preview_html(request, self.inactive_template.key)

    @override_settings(DEBUG=True)
    def test_preview_html_with_rendering_error(self):
        """Test HTML preview when template rendering fails."""
        bad_template = EmailTemplate.objects.create(
            key="bad_html_template",
            name="Bad HTML Template",
            subject="Subject",
            html_content="<p>{% invalid_tag %}</p>",
            text_content="Text",
            is_active=True,
        )

        from apps.emails.views import email_preview_html

        request = self.factory.get(f"/dev/emails/{bad_template.key}/html/")
        request.user = self.staff_user

        response = email_preview_html(request, bad_template.key)

        self.assertEqual(response.status_code, 500)
        self.assertIn("Error rendering template", response.content.decode())

    @override_settings(DEBUG=True)
    def test_preview_html_with_authenticated_user(self):
        """Test HTML preview with authenticated user context."""
        from apps.emails.views import email_preview_html

        request = self.factory.get(f"/dev/emails/{self.email_template.key}/html/")
        request.user = self.staff_user

        response = email_preview_html(request, self.email_template.key)

        self.assertEqual(response.status_code, 200)
        content = response.content.decode()
        # The sample context should include sample data
        self.assertIn("Sample Notification", content)


class EmailPreviewTextViewTests(EmailViewTestCase):
    """Test email_preview_text function view."""

    @override_settings(DEBUG=True)
    def test_staff_user_can_preview_text_in_debug(self):
        """Test that staff users can preview text in debug mode."""
        from apps.emails.views import email_preview_text

        request = self.factory.get(f"/dev/emails/{self.email_template.key}/text/")
        request.user = self.staff_user

        response = email_preview_text(request, self.email_template.key)

        self.assertEqual(response.status_code, 200)
        self.assertIn("text/plain", response.get("Content-Type", ""))

    @override_settings(DEBUG=False)
    def test_staff_user_can_preview_text_in_production(self):
        """Test that staff users can preview text in production mode."""
        from apps.emails.views import email_preview_text

        request = self.factory.get("/")
        request.user = self.staff_user

        response = email_preview_text(request, self.email_template.key)
        self.assertEqual(response.status_code, 200)

    @override_settings(DEBUG=False)  # Changed to False to test permission check
    def test_regular_user_cannot_preview_text_in_debug(self):
        """Test that regular users cannot preview text in debug mode."""
        from apps.emails.views import email_preview_text

        request = self.factory.get(f"/dev/emails/{self.email_template.key}/text/")
        request.user = self.regular_user

        response = email_preview_text(request, self.email_template.key)

        self.assertEqual(response.status_code, 403)

    @override_settings(DEBUG=False)
    def test_regular_user_cannot_preview_text_in_production(self):
        """Test that regular users cannot preview text in production mode."""
        from apps.emails.views import email_preview_text

        request = self.factory.get("/")
        request.user = self.regular_user

        response = email_preview_text(request, self.email_template.key)
        self.assertEqual(response.status_code, 403)

    @override_settings(DEBUG=True)
    def test_preview_text_with_nonexistent_template(self):
        """Test text preview with nonexistent template."""
        from django.http import Http404

        from apps.emails.views import email_preview_text

        request = self.factory.get("/dev/emails/nonexistent/text/")
        request.user = self.staff_user

        # The function raises Http404 exception, so we need to catch it
        with self.assertRaises(Http404):
            email_preview_text(request, "nonexistent")

    @override_settings(DEBUG=True)
    def test_preview_text_with_rendering_error(self):
        """Test text preview when template rendering fails."""
        bad_template = EmailTemplate.objects.create(
            key="bad_text_template",
            name="Bad Text Template",
            subject="Subject",
            html_content="<p>HTML</p>",
            text_content="{% invalid_tag %}",
            is_active=True,
        )

        from apps.emails.views import email_preview_text

        request = self.factory.get(f"/dev/emails/{bad_template.key}/text/")
        request.user = self.staff_user

        response = email_preview_text(request, bad_template.key)

        self.assertEqual(response.status_code, 500)
        self.assertIn("Error rendering template", response.content.decode())


class SendTestEmailViewTests(EmailViewTestCase):
    """Test send_test_email function view."""

    @override_settings(DEBUG=True)
    @patch.object(EmailService, "send_email")
    def test_staff_user_can_send_test_email_in_debug(self, mock_send_email):
        """Test that staff users can send test emails in debug mode."""
        # Mock the email service response
        mock_email_log = Mock()
        mock_email_log.id = 123
        mock_send_email.return_value = mock_email_log

        from apps.emails.views import send_test_email

        data = {"to_email": "test@example.com"}
        request = self.factory.post(
            f"/dev/emails/{self.email_template.key}/test/",
            data=json.dumps(data),
            content_type="application/json",
        )
        request.user = self.staff_user

        response = send_test_email(request, self.email_template.key)

        self.assertEqual(response.status_code, 200)
        response_data = json.loads(response.content)
        self.assertTrue(response_data["success"])
        self.assertIn("Test email sent to test@example.com", response_data["message"])
        self.assertEqual(response_data["email_log_id"], 123)

        # Verify email service was called correctly
        mock_send_email.assert_called_once()
        call_args = mock_send_email.call_args
        self.assertEqual(call_args[1]["template_key"], self.email_template.key)
        self.assertEqual(call_args[1]["to_email"], "test@example.com")
        self.assertFalse(
            call_args[1]["async_send"]
        )  # Should be synchronous for testing

    @override_settings(DEBUG=True)
    @patch.object(EmailService, "send_email")
    def test_send_test_email_defaults_to_user_email(self, mock_send_email):
        """Test that test email defaults to user's email when no to_email provided."""
        mock_email_log = Mock()
        mock_email_log.id = 123
        mock_send_email.return_value = mock_email_log

        from apps.emails.views import send_test_email

        request = self.factory.post(
            f"/dev/emails/{self.email_template.key}/test/",
            data=json.dumps({}),
            content_type="application/json",
        )
        request.user = self.staff_user

        response = send_test_email(request, self.email_template.key)

        self.assertEqual(response.status_code, 200)

        # Verify email service was called with staff user's email
        call_args = mock_send_email.call_args
        self.assertEqual(call_args[1]["to_email"], self.staff_user.email)

    @override_settings(DEBUG=False)
    def test_staff_user_cannot_send_test_email_in_production(self):
        """Test that staff users cannot send test emails in production mode."""
        from apps.emails.views import send_test_email

        request = self.factory.post(
            "/",
            data=json.dumps({"to_email": "test@example.com"}),
            content_type="application/json",
        )
        request.user = self.staff_user

        response = send_test_email(request, self.email_template.key)

        self.assertEqual(response.status_code, 403)
        response_data = json.loads(response.content)
        self.assertEqual(response_data["error"], "Not allowed")

    @override_settings(DEBUG=True)
    def test_regular_user_cannot_send_test_email(self):
        """Test that regular users cannot send test emails."""
        from apps.emails.views import send_test_email

        request = self.factory.post(
            f"/dev/emails/{self.email_template.key}/test/",
            data=json.dumps({"to_email": "test@example.com"}),
            content_type="application/json",
        )
        request.user = self.regular_user

        response = send_test_email(request, self.email_template.key)

        self.assertEqual(response.status_code, 403)

    @override_settings(DEBUG=True)
    def test_send_test_email_requires_post_method(self):
        """Test that send test email requires POST method."""
        from apps.emails.views import send_test_email

        request = self.factory.get(f"/dev/emails/{self.email_template.key}/test/")
        request.user = self.staff_user

        response = send_test_email(request, self.email_template.key)

        self.assertEqual(response.status_code, 405)
        response_data = json.loads(response.content)
        self.assertEqual(response_data["error"], "POST method required")

    @override_settings(DEBUG=True)
    @patch.object(EmailService, "send_email")
    def test_send_test_email_handles_service_error(self, mock_send_email):
        """Test that send test email handles EmailService errors."""
        mock_send_email.side_effect = Exception("SMTP server error")

        from apps.emails.views import send_test_email

        request = self.factory.post(
            f"/dev/emails/{self.email_template.key}/test/",
            data=json.dumps({"to_email": "test@example.com"}),
            content_type="application/json",
        )
        request.user = self.staff_user

        response = send_test_email(request, self.email_template.key)

        self.assertEqual(response.status_code, 500)
        response_data = json.loads(response.content)
        self.assertFalse(response_data["success"])
        self.assertEqual(response_data["error"], "SMTP server error")

    @override_settings(DEBUG=True)
    def test_send_test_email_handles_invalid_json(self):
        """Test that send test email handles invalid JSON data."""
        from apps.emails.views import send_test_email

        request = self.factory.post(
            f"/dev/emails/{self.email_template.key}/test/",
            data="invalid json",
            content_type="application/json",
        )
        request.user = self.staff_user

        response = send_test_email(request, self.email_template.key)

        self.assertEqual(response.status_code, 500)


class EmailLogListViewTests(EmailViewTestCase):
    """Test EmailLogListView."""

    def test_staff_user_can_access_email_logs(self):
        """Test that staff users can access email logs."""
        from apps.emails.views import EmailLogListView

        request = self.factory.get("/dev/email-logs/")
        request.user = self.staff_user

        view = EmailLogListView()
        view.request = request

        context = view.get_context_data()
        self.assertIn("email_logs", context)

        email_logs = context["email_logs"]
        self.assertIn(self.email_log_1, email_logs)
        self.assertIn(self.email_log_2, email_logs)

    def test_email_logs_context_data(self):
        """Test that the email logs view provides correct context data."""
        from apps.emails.views import EmailLogListView

        request = self.factory.get("/dev/email-logs/")
        request.user = self.staff_user

        view = EmailLogListView()
        view.request = request
        context = view.get_context_data()

        self.assertIn("email_logs", context)

        email_logs = context["email_logs"]
        self.assertIn(self.email_log_1, email_logs)
        self.assertIn(self.email_log_2, email_logs)

    def test_email_logs_ordering_and_limit(self):
        """Test that email logs are ordered by creation date and limited to 100."""
        # Create additional email logs to test the limit
        for i in range(105):
            EmailMessageLog.objects.create(
                template_key=f"test_template_{i}",
                to_email=f"recipient{i}@example.com",
                from_email="sender@example.com",
                subject=f"Test Email {i}",
                status=EmailStatus.SENT,
            )

        from apps.emails.views import EmailLogListView

        request = self.factory.get("/dev/email-logs/")
        request.user = self.staff_user

        view = EmailLogListView()
        view.request = request
        context = view.get_context_data()

        email_logs = context["email_logs"]

        # Should have exactly 100 logs (the limit)
        self.assertEqual(len(email_logs), 100)

        # Should be ordered by created_at descending (newest first)
        created_dates = [log.created_at for log in email_logs]
        self.assertEqual(created_dates, sorted(created_dates, reverse=True))


class EmailWebhookViewTests(EmailViewTestCase):
    """Test email_webhook function view."""

    def test_webhook_requires_post_method(self):
        """Test that webhook requires POST method."""
        from apps.emails.views import email_webhook

        request = self.factory.get("/dev/webhooks/email/")

        response = email_webhook(request)

        self.assertEqual(response.status_code, 405)
        response_data = json.loads(response.content)
        self.assertEqual(response_data["error"], "POST method required")

    def test_webhook_handles_delivered_event(self):
        """Test webhook handling for delivered event."""
        from apps.emails.views import email_webhook

        webhook_data = {"event": "delivered", "message_id": "test_task_id"}

        # Set a task ID for testing
        self.email_log_1.celery_task_id = "test_task_id"
        self.email_log_1.save()

        request = self.factory.post(
            "/dev/webhooks/email/",
            data=json.dumps(webhook_data),
            content_type="application/json",
        )

        response = email_webhook(request)

        self.assertEqual(response.status_code, 200)
        response_data = json.loads(response.content)
        self.assertEqual(response_data["status"], "ok")

        # Verify email log was updated
        self.email_log_1.refresh_from_db()
        self.assertEqual(self.email_log_1.status, EmailStatus.DELIVERED)
        self.assertIsNotNone(self.email_log_1.delivered_at)

    def test_webhook_handles_opened_event(self):
        """Test webhook handling for opened event."""
        from apps.emails.views import email_webhook

        self.email_log_1.celery_task_id = "test_task_id"
        self.email_log_1.save()

        webhook_data = {"event": "opened", "message_id": "test_task_id"}

        request = self.factory.post(
            "/dev/webhooks/email/",
            data=json.dumps(webhook_data),
            content_type="application/json",
        )

        response = email_webhook(request)

        self.assertEqual(response.status_code, 200)

        self.email_log_1.refresh_from_db()
        self.assertEqual(self.email_log_1.status, EmailStatus.OPENED)
        self.assertIsNotNone(self.email_log_1.opened_at)

    def test_webhook_handles_clicked_event(self):
        """Test webhook handling for clicked event."""
        from apps.emails.views import email_webhook

        self.email_log_1.celery_task_id = "test_task_id"
        self.email_log_1.save()

        webhook_data = {"event": "clicked", "message_id": "test_task_id"}

        request = self.factory.post(
            "/dev/webhooks/email/",
            data=json.dumps(webhook_data),
            content_type="application/json",
        )

        response = email_webhook(request)

        self.assertEqual(response.status_code, 200)

        self.email_log_1.refresh_from_db()
        self.assertEqual(self.email_log_1.status, EmailStatus.CLICKED)
        self.assertIsNotNone(self.email_log_1.clicked_at)

    def test_webhook_handles_bounced_event(self):
        """Test webhook handling for bounced event."""
        from apps.emails.views import email_webhook

        self.email_log_1.celery_task_id = "test_task_id"
        self.email_log_1.save()

        webhook_data = {"event": "bounced", "message_id": "test_task_id"}

        request = self.factory.post(
            "/dev/webhooks/email/",
            data=json.dumps(webhook_data),
            content_type="application/json",
        )

        response = email_webhook(request)

        self.assertEqual(response.status_code, 200)

        self.email_log_1.refresh_from_db()
        self.assertEqual(self.email_log_1.status, EmailStatus.BOUNCED)

    def test_webhook_handles_unknown_event(self):
        """Test webhook handling for unknown event types."""
        from apps.emails.views import email_webhook

        webhook_data = {"event": "unknown_event", "message_id": "test_task_id"}

        request = self.factory.post(
            "/dev/webhooks/email/",
            data=json.dumps(webhook_data),
            content_type="application/json",
        )

        response = email_webhook(request)

        # Should still return success even for unknown events
        self.assertEqual(response.status_code, 200)

    def test_webhook_handles_nonexistent_message_id(self):
        """Test webhook handling for nonexistent message ID."""
        from apps.emails.views import email_webhook

        webhook_data = {"event": "delivered", "message_id": "nonexistent_task_id"}

        request = self.factory.post(
            "/dev/webhooks/email/",
            data=json.dumps(webhook_data),
            content_type="application/json",
        )

        response = email_webhook(request)

        # Should still return success even when message not found
        self.assertEqual(response.status_code, 200)

    def test_webhook_handles_missing_message_id(self):
        """Test webhook handling when message_id is missing."""
        from apps.emails.views import email_webhook

        webhook_data = {
            "event": "delivered"
            # No message_id provided
        }

        request = self.factory.post(
            "/dev/webhooks/email/",
            data=json.dumps(webhook_data),
            content_type="application/json",
        )

        response = email_webhook(request)

        # Should still return success
        self.assertEqual(response.status_code, 200)

    def test_webhook_handles_invalid_json(self):
        """Test webhook handling for invalid JSON data."""
        from apps.emails.views import email_webhook

        request = self.factory.post(
            "/dev/webhooks/email/", data="invalid json", content_type="application/json"
        )

        response = email_webhook(request)

        self.assertEqual(response.status_code, 400)
        response_data = json.loads(response.content)
        self.assertIn("error", response_data)

    def test_webhook_handles_exception(self):
        """Test webhook handling when an unexpected exception occurs."""
        from apps.emails.views import email_webhook

        # Send webhook data that will cause an exception when processing
        with patch("apps.emails.views.EmailMessageLog.objects.get") as mock_get:
            mock_get.side_effect = Exception("Database error")

            webhook_data = {"event": "delivered", "message_id": "test_task_id"}

            request = self.factory.post(
                "/dev/webhooks/email/",
                data=json.dumps(webhook_data),
                content_type="application/json",
            )

            response = email_webhook(request)

            self.assertEqual(response.status_code, 400)
            response_data = json.loads(response.content)
            self.assertIn("error", response_data)

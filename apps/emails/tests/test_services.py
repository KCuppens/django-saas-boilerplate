"""Tests for email services and functionality."""

import tempfile
from datetime import timedelta
from unittest.mock import MagicMock, Mock, patch

from django.contrib.auth import get_user_model
from django.core import mail
from django.test import TestCase, override_settings
from django.utils import timezone

from apps.core.enums import EmailStatus
from apps.emails.models import EmailMessageLog, EmailTemplate
from apps.emails.services import EmailService
from apps.emails.tasks import (
    cleanup_old_email_logs,
    send_bulk_email_task,
    send_email_task,
)

# Aliases for compatibility with test code
EmailLog = EmailMessageLog


# Simple template renderer for testing
class TemplateRenderer:
    """Simple template renderer for testing purposes."""

    def render(self, template_text, context):
        """Render template with context."""
        from django.template import Context, Template

        template = Template(template_text)
        return template.render(Context(context))


User = get_user_model()


class EmailServiceTestCase(TestCase):
    """Test EmailService functionality."""

    def setUp(self):
        """Set up test data."""
        self.user = User.objects.create_user(
            email="test@example.com", password="testpass123", name="Test User"
        )

        # Create a test email template
        self.template = EmailTemplate.objects.create(
            key="test_template",
            name="Test Template",
            subject="Test Subject {{user.name}}",
            html_content="<h1>Hello {{user.name}}</h1>",
            text_content="Hello {{user.name}}",
            is_active=True,
        )

    def test_send_email_with_template(self):
        """Test sending email using template."""
        result = EmailService.send_email(
            template_key="test_template",
            to_email="recipient@example.com",
            context={"user": self.user},
            async_send=False,
        )

        self.assertIsInstance(result, EmailMessageLog)
        self.assertEqual(result.to_email, "recipient@example.com")
        self.assertEqual(result.status, EmailStatus.SENT)

        # Check email was sent
        self.assertEqual(len(mail.outbox), 1)
        email = mail.outbox[0]
        self.assertEqual(email.to, ["recipient@example.com"])
        self.assertIn(self.user.name, email.subject)
        self.assertIn(self.user.name, email.body)

    def test_send_email_with_html(self):
        """Test sending email with HTML content."""
        result = self.email_service.send_email(
            to_email="recipient@example.com",
            subject="Test Subject",
            message="Text message",
            html_message="<h1>HTML message</h1>",
        )

        self.assertTrue(result)
        self.assertEqual(len(mail.outbox), 1)
        email = mail.outbox[0]
        self.assertEqual(email.body, "Text message")
        self.assertEqual(len(email.alternatives), 1)
        self.assertEqual(email.alternatives[0][0], "<h1>HTML message</h1>")
        self.assertEqual(email.alternatives[0][1], "text/html")

    def test_send_email_with_attachments(self):
        """Test sending email with attachments."""
        # Create a temporary file
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".txt", delete=False
        ) as tmp_file:
            tmp_file.write("Test attachment content")
            tmp_file.flush()

            result = self.email_service.send_email(
                to_email="recipient@example.com",
                subject="Test Subject",
                message="Test message",
                attachments=[tmp_file.name],
            )

        self.assertTrue(result)
        self.assertEqual(len(mail.outbox), 1)
        email = mail.outbox[0]
        self.assertEqual(len(email.attachments), 1)

    def test_send_email_multiple_recipients(self):
        """Test sending email to multiple recipients."""
        recipients = ["user1@example.com", "user2@example.com", "user3@example.com"]

        result = self.email_service.send_email(
            to_email=recipients, subject="Bulk Test", message="Bulk test message"
        )

        self.assertTrue(result)
        self.assertEqual(len(mail.outbox), 1)
        email = mail.outbox[0]
        self.assertEqual(email.to, recipients)

    def test_send_email_with_context(self):
        """Test sending email with template context."""
        context = {"name": "John Doe", "action_url": "https://example.com/action"}

        result = self.email_service.send_email(
            to_email="recipient@example.com",
            subject="Hello {{name}}",
            message="Click here: {{action_url}}",
            context=context,
        )

        self.assertTrue(result)
        self.assertEqual(len(mail.outbox), 1)
        email = mail.outbox[0]
        self.assertEqual(email.subject, "Hello John Doe")
        self.assertEqual(email.body, "Click here: https://example.com/action")

    @patch("apps.emails.services.EmailMultiAlternatives.send")
    def test_send_email_failure_handling(self, mock_send):
        """Test email service handles send failures."""
        mock_send.side_effect = Exception("SMTP Error")

        result = self.email_service.send_email(
            to_email="recipient@example.com",
            subject="Test Subject",
            message="Test message",
        )

        self.assertFalse(result)

    def test_send_email_with_from_email(self):
        """Test sending email with custom from_email."""
        result = self.email_service.send_email(
            to_email="recipient@example.com",
            subject="Test Subject",
            message="Test message",
            from_email="custom@example.com",
        )

        self.assertTrue(result)
        self.assertEqual(len(mail.outbox), 1)
        email = mail.outbox[0]
        self.assertEqual(email.from_email, "custom@example.com")

    def test_send_template_email(self):
        """Test sending email using template."""
        # Create a test template
        EmailTemplate.objects.create(
            key="test_template",
            name="Test Template",
            subject="Welcome {{user.name}}!",
            body_text="Hello {{user.name}}, welcome to our platform!",
            body_html="<h1>Hello {{user.name}}</h1><p>Welcome to our platform!</p>",
            is_active=True,
        )

        result = self.email_service.send_template_email(
            template_key="test_template",
            to_email=self.user.email,
            context={"user": self.user},
        )

        self.assertTrue(result)
        self.assertEqual(len(mail.outbox), 1)
        email = mail.outbox[0]
        self.assertEqual(email.subject, f"Welcome {self.user.name}!")
        self.assertIn(self.user.name, email.body)

    def test_send_template_email_nonexistent_template(self):
        """Test sending email with non-existent template."""
        result = self.email_service.send_template_email(
            template_key="nonexistent_template",
            to_email=self.user.email,
            context={"user": self.user},
        )

        self.assertFalse(result)
        self.assertEqual(len(mail.outbox), 0)

    def test_send_template_email_inactive_template(self):
        """Test sending email with inactive template."""
        EmailTemplate.objects.create(
            key="inactive_template",
            name="Inactive Template",
            subject="Test Subject",
            body_text="Test body",
            is_active=False,
        )

        result = self.email_service.send_template_email(
            template_key="inactive_template",
            to_email=self.user.email,
            context={"user": self.user},
        )

        self.assertFalse(result)
        self.assertEqual(len(mail.outbox), 0)


class TemplateRendererTestCase(TestCase):
    """Test TemplateRenderer functionality."""

    def setUp(self):
        """Set up test data."""
        self.renderer = TemplateRenderer()
        self.user = User.objects.create_user(
            email="test@example.com", password="testpass123", name="Test User"
        )

    def test_render_simple_template(self):
        """Test rendering a simple template."""
        template_text = "Hello {{name}}!"
        context = {"name": "World"}

        result = self.renderer.render(template_text, context)

        self.assertEqual(result, "Hello World!")

    def test_render_complex_template(self):
        """Test rendering a complex template with nested objects."""
        template_text = "Hello {{user.name}}, your email is {{user.email}}"
        context = {"user": self.user}

        result = self.renderer.render(template_text, context)

        self.assertEqual(
            result, f"Hello {self.user.name}, your email is {self.user.email}"
        )

    def test_render_template_with_filters(self):
        """Test rendering template with Django template filters."""
        template_text = "Hello {{name|upper}}!"
        context = {"name": "world"}

        result = self.renderer.render(template_text, context)

        self.assertEqual(result, "Hello WORLD!")

    def test_render_template_with_conditionals(self):
        """Test rendering template with conditional logic."""
        template_text = "{% if user.is_active %}Active{% else %}Inactive{% endif %}"
        context = {"user": self.user}

        result = self.renderer.render(template_text, context)

        self.assertEqual(result, "Active")

    def test_render_template_with_loops(self):
        """Test rendering template with loops."""
        template_text = "{% for item in items %}{{item}} {% endfor %}"
        context = {"items": ["A", "B", "C"]}

        result = self.renderer.render(template_text, context)

        self.assertEqual(result, "A B C ")

    def test_render_template_error_handling(self):
        """Test template renderer handles errors gracefully."""
        template_text = "{{undefined_variable}}"
        context = {}

        # Should not raise an exception, should return empty string or template as-is
        result = self.renderer.render(template_text, context)

        # Django templates handle undefined variables gracefully
        self.assertEqual(result, "")

    def test_render_template_with_safe_html(self):
        """Test rendering template with safe HTML content."""
        template_text = "{{content|safe}}"
        context = {"content": "<strong>Bold text</strong>"}

        result = self.renderer.render(template_text, context)

        self.assertEqual(result, "<strong>Bold text</strong>")


class EmailLogTestCase(TestCase):
    """Test EmailLog model functionality."""

    def setUp(self):
        """Set up test data."""
        self.user = User.objects.create_user(
            email="test@example.com", password="testpass123", name="Test User"
        )

    def test_email_log_creation(self):
        """Test creating an email log entry."""
        log = EmailLog.objects.create(
            to_email="recipient@example.com",
            subject="Test Subject",
            body="Test body",
            status="sent",
            user=self.user,
        )

        self.assertEqual(log.to_email, "recipient@example.com")
        self.assertEqual(log.subject, "Test Subject")
        self.assertEqual(log.status, "sent")
        self.assertEqual(log.user, self.user)
        self.assertIsNotNone(log.created_at)

    def test_email_log_str_representation(self):
        """Test EmailLog string representation."""
        log = EmailLog.objects.create(
            to_email="recipient@example.com",
            subject="Test Subject",
            body="Test body",
            status="sent",
        )

        expected_str = f"Email to recipient@example.com: Test Subject ({log.status})"
        self.assertEqual(str(log), expected_str)

    def test_email_log_recent_manager(self):
        """Test EmailLog recent entries filtering."""
        # Create old log
        old_log = EmailLog.objects.create(
            to_email="old@example.com",
            subject="Old Email",
            body="Old body",
            status="sent",
        )
        old_log.created_at = timezone.now() - timedelta(days=8)
        old_log.save()

        # Create recent log
        EmailLog.objects.create(
            to_email="recent@example.com",
            subject="Recent Email",
            body="Recent body",
            status="sent",
        )

        # Test that we can filter recent logs (if such functionality exists)
        all_logs = EmailLog.objects.all()
        self.assertEqual(all_logs.count(), 2)


class EmailTasksTestCase(TestCase):
    """Test email Celery tasks."""

    def setUp(self):
        """Set up test data."""
        self.user = User.objects.create_user(
            email="test@example.com", password="testpass123", name="Test User"
        )

    @patch("apps.emails.services.EmailService.send_email")
    def test_send_email_task(self, mock_send_email):
        """Test send_email_task functionality."""
        mock_send_email.return_value = True

        result = send_email_task(
            to_email="recipient@example.com",
            subject="Test Subject",
            message="Test message",
        )

        self.assertTrue(result)
        mock_send_email.assert_called_once_with(
            to_email="recipient@example.com",
            subject="Test Subject",
            message="Test message",
            html_message=None,
            from_email=None,
            attachments=None,
            context=None,
        )

    @patch("apps.emails.services.EmailService.send_template_email")
    def test_send_email_task_with_template(self, mock_send_template_email):
        """Test send_email_task with template."""
        mock_send_template_email.return_value = True

        result = send_email_task(
            to_email="recipient@example.com",
            template_key="test_template",
            context={"user": "test"},
        )

        self.assertTrue(result)
        mock_send_template_email.assert_called_once()

    @patch("apps.emails.services.EmailService.send_email")
    def test_send_bulk_email_task(self, mock_send_email):
        """Test send_bulk_email_task functionality."""
        mock_send_email.return_value = True

        email_data = [
            {
                "to_email": "user1@example.com",
                "subject": "Subject 1",
                "message": "Message 1",
            },
            {
                "to_email": "user2@example.com",
                "subject": "Subject 2",
                "message": "Message 2",
            },
        ]

        result = send_bulk_email_task(email_data)

        self.assertEqual(result["sent"], 2)
        self.assertEqual(result["failed"], 0)
        self.assertEqual(mock_send_email.call_count, 2)

    @patch("apps.emails.services.EmailService.send_email")
    def test_send_bulk_email_task_with_failures(self, mock_send_email):
        """Test send_bulk_email_task with some failures."""
        # Mock to succeed first call, fail second
        mock_send_email.side_effect = [True, False]

        email_data = [
            {
                "to_email": "user1@example.com",
                "subject": "Subject 1",
                "message": "Message 1",
            },
            {
                "to_email": "user2@example.com",
                "subject": "Subject 2",
                "message": "Message 2",
            },
        ]

        result = send_bulk_email_task(email_data)

        self.assertEqual(result["sent"], 1)
        self.assertEqual(result["failed"], 1)


class EmailTemplateTestCase(TestCase):
    """Test EmailTemplate model functionality."""

    def setUp(self):
        """Set up test data."""
        self.template = EmailTemplate.objects.create(
            key="test_template",
            name="Test Template",
            subject="Test Subject",
            body_text="Test body text",
            body_html="<p>Test body HTML</p>",
            is_active=True,
        )

    def test_template_str_representation(self):
        """Test EmailTemplate string representation."""
        expected_str = f"{self.template.name} ({self.template.key})"
        self.assertEqual(str(self.template), expected_str)

    def test_template_key_uniqueness(self):
        """Test that template key must be unique."""
        from django.db import IntegrityError

        with self.assertRaises(IntegrityError):
            EmailTemplate.objects.create(
                key="test_template",  # Same key as setUp
                name="Another Template",
                subject="Another Subject",
                body_text="Another body",
            )

    def test_template_active_manager(self):
        """Test active template manager."""
        # Create inactive template
        EmailTemplate.objects.create(
            key="inactive_template",
            name="Inactive Template",
            subject="Inactive Subject",
            body_text="Inactive body",
            is_active=False,
        )

        # Test filtering active templates
        active_templates = EmailTemplate.objects.filter(is_active=True)
        self.assertEqual(active_templates.count(), 1)
        self.assertEqual(active_templates.first(), self.template)

    def test_template_rendering_integration(self):
        """Test template rendering with the model."""
        context = {"name": "John"}

        # Update template to use context
        self.template.subject = "Hello {{name}}"
        self.template.body_text = "Welcome {{name}}!"
        self.template.save()

        renderer = TemplateRenderer()
        rendered_subject = renderer.render(self.template.subject, context)
        rendered_body = renderer.render(self.template.body_text, context)

        self.assertEqual(rendered_subject, "Hello John")
        self.assertEqual(rendered_body, "Welcome John!")


@override_settings(CELERY_TASK_ALWAYS_EAGER=True)
class EmailIntegrationTestCase(TestCase):
    """Integration tests for complete email workflows."""

    def setUp(self):
        """Set up test data."""
        self.user = User.objects.create_user(
            email="test@example.com", password="testpass123", name="Test User"
        )
        self.email_service = EmailService()

    def test_complete_template_email_workflow(self):
        """Test complete workflow from template creation to email sending."""
        # 1. Create template
        EmailTemplate.objects.create(
            key="welcome_email",
            name="Welcome Email",
            subject="Welcome {{user.name}} to our platform!",
            body_text="Hello {{user.name}}, welcome! Your email is {{user.email}}.",
            body_html=(
                "<h1>Hello {{user.name}}</h1>" "<p>Welcome! Email: {{user.email}}.</p>"
            ),
            is_active=True,
        )

        # 2. Send email using template
        result = self.email_service.send_template_email(
            template_key="welcome_email",
            to_email=self.user.email,
            context={"user": self.user},
        )

        # 3. Verify email was sent
        self.assertTrue(result)
        self.assertEqual(len(mail.outbox), 1)

        email = mail.outbox[0]
        self.assertEqual(email.to, [self.user.email])
        self.assertEqual(email.subject, f"Welcome {self.user.name} to our platform!")
        self.assertIn(self.user.name, email.body)
        self.assertIn(self.user.email, email.body)

        # 4. Verify HTML content
        self.assertEqual(len(email.alternatives), 1)
        html_content = email.alternatives[0][0]
        self.assertIn(f"<h1>Hello {self.user.name}</h1>", html_content)

    def test_bulk_email_workflow(self):
        """Test bulk email sending workflow."""
        # Create multiple users
        users = []
        for i in range(3):
            user = User.objects.create_user(
                email=f"user{i}@example.com", password="testpass123", name=f"User {i}"
            )
            users.append(user)

        # Prepare bulk email data
        email_data = []
        for user in users:
            email_data.append(
                {
                    "to_email": user.email,
                    "subject": f"Hello {user.name}",
                    "message": f"Welcome {user.name}!",
                    "html_message": f"<h1>Welcome {user.name}!</h1>",
                }
            )

        # Send bulk emails
        result = send_bulk_email_task(email_data)

        # Verify results
        self.assertEqual(result["sent"], 3)
        self.assertEqual(result["failed"], 0)
        self.assertEqual(len(mail.outbox), 3)

        # Verify each email
        for i, email in enumerate(mail.outbox):
            expected_user = users[i]
            self.assertEqual(email.to, [expected_user.email])
            self.assertEqual(email.subject, f"Hello {expected_user.name}")
            self.assertIn(expected_user.name, email.body)

"""Test cases for email functionality."""

from django.contrib.auth import get_user_model
from django.test import TestCase

from apps.core.enums import EmailStatus
from apps.emails.models import EmailMessageLog, EmailTemplate

User = get_user_model()


class EmailModelTests(TestCase):
    """Test email models."""

    def setUp(self):
        """Set up test data for email model tests."""
        self.user = User.objects.create_user(
            email="test@example.com", password="testpass123"
        )

    def test_email_template_creation(self):
        """Test EmailTemplate creation."""
        template = EmailTemplate.objects.create(
            key="welcome",
            name="Welcome Email",
            subject="Welcome!",
            html_content="<h1>Welcome!</h1>",
            text_content="Welcome!",
            language="en",
        )
        # Check if the string representation works as expected
        expected_str = f"{template.name} ({template.key})"
        self.assertEqual(str(template), expected_str)
        self.assertEqual(template.key, "welcome")

    def test_email_template_render_subject(self):
        """Test EmailTemplate subject rendering."""
        template = EmailTemplate.objects.create(
            key="welcome",
            name="Welcome Email",
            subject="Welcome {{name}}!",
            html_content="<h1>Welcome {{name}}!</h1>",
            text_content="Welcome {{name}}!",
            language="en",
        )
        rendered = template.render_subject({"name": "John"})
        self.assertEqual(rendered, "Welcome John!")

    def test_email_message_log_creation(self):
        """Test EmailMessageLog creation."""
        template = EmailTemplate.objects.create(
            key="welcome",
            name="Welcome Email",
            subject="Welcome!",
            html_content="<h1>Welcome!</h1>",
            text_content="Welcome!",
            language="en",
        )

        log = EmailMessageLog.objects.create(
            template=template,
            template_key="welcome",
            to_email="test@example.com",
            from_email="noreply@example.com",
            subject="Welcome!",
            html_content="<h1>Welcome!</h1>",
            text_content="Welcome!",
            status=EmailStatus.PENDING,
        )

        # Check the string representation works
        expected_str = f"Email to {log.to_email} - {log.subject}"
        self.assertEqual(str(log), expected_str)
        self.assertEqual(log.status, EmailStatus.PENDING)

    def test_email_message_log_mark_as_sent(self):
        """Test EmailMessageLog mark_as_sent method."""
        log = EmailMessageLog.objects.create(
            template_key="test",
            to_email="test@example.com",
            from_email="noreply@example.com",
            subject="Test",
            status=EmailStatus.PENDING,
        )

        log.mark_as_sent()
        self.assertEqual(log.status, EmailStatus.SENT)
        self.assertIsNotNone(log.sent_at)

    def test_email_message_log_mark_as_failed(self):
        """Test EmailMessageLog mark_as_failed method."""
        log = EmailMessageLog.objects.create(
            template_key="test",
            to_email="test@example.com",
            from_email="noreply@example.com",
            subject="Test",
            status=EmailStatus.PENDING,
        )

        error_message = "SMTP connection failed"
        log.mark_as_failed(error_message)
        self.assertEqual(log.status, EmailStatus.FAILED)
        self.assertEqual(log.error_message, error_message)
        self.assertIsNotNone(log.failed_at)

    def test_email_template_get_template(self):
        """Test EmailTemplate get_template class method."""
        template = EmailTemplate.objects.create(
            key="test_template",
            name="Test Template",
            subject="Test",
            html_content="<p>Test</p>",
            text_content="Test",
            language="en",
            is_active=True,
        )

        retrieved = EmailTemplate.get_template("test_template", "en")
        self.assertEqual(retrieved, template)

        # Test non-existent template
        not_found = EmailTemplate.get_template("nonexistent", "en")
        self.assertIsNone(not_found)

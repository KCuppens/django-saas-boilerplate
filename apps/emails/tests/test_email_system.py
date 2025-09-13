"""Comprehensive tests for email system functionality."""

from datetime import timedelta
from unittest.mock import Mock, patch

from django.contrib.auth import get_user_model
from django.core import mail
from django.test import TestCase, override_settings
from django.utils import timezone

from apps.core.enums import EmailStatus
from apps.emails.models import EmailMessageLog, EmailTemplate
from apps.emails.services import (
    EmailService,
    send_password_reset_email,
    send_welcome_email,
)
from apps.emails.tasks import (
    cleanup_old_email_logs,
    send_bulk_email_task,
    send_email_task,
)

User = get_user_model()


class EmailTemplateTestCase(TestCase):
    """Test EmailTemplate model functionality."""

    def setUp(self):
        """Set up test data."""
        self.user = User.objects.create_user(
            email="test@example.com", password="testpass123", name="Test User"
        )

    def test_email_template_creation(self):
        """Test creating an email template."""
        template = EmailTemplate.objects.create(
            key="welcome",
            name="Welcome Email",
            subject="Welcome {{user.name}}!",
            html_content="<h1>Welcome {{user.name}}!</h1>",
            text_content="Welcome {{user.name}}!",
            is_active=True,
        )

        self.assertEqual(template.key, "welcome")
        self.assertEqual(template.name, "Welcome Email")
        self.assertTrue(template.is_active)

    def test_email_template_rendering(self):
        """Test email template rendering."""
        template = EmailTemplate.objects.create(
            key="test_template",
            name="Test Template",
            subject="Hello {{user.name}}",
            html_content="<p>Hello {{user.name}}, your email is {{user.email}}</p>",
            text_content="Hello {{user.name}}, your email is {{user.email}}",
            is_active=True,
        )

        context = {"user": self.user}
        rendered = template.render_all(context)

        self.assertEqual(rendered["subject"], f"Hello {self.user.name}")
        self.assertIn(self.user.name, rendered["html_content"])
        self.assertIn(self.user.email, rendered["html_content"])
        self.assertIn(self.user.name, rendered["text_content"])

    def test_email_template_cache_functionality(self):
        """Test email template caching."""
        template = EmailTemplate.objects.create(
            key="cached_template",
            name="Cached Template",
            subject="Test Subject",
            html_content="<p>Test</p>",
            text_content="Test",
            is_active=True,
        )

        # Test get_template method
        cached_template = EmailTemplate.get_template("cached_template")
        self.assertEqual(cached_template.id, template.id)

        # Test non-existent template
        none_template = EmailTemplate.get_template("nonexistent")
        self.assertIsNone(none_template)

    def test_email_template_inactive(self):
        """Test that inactive templates are not retrieved."""
        EmailTemplate.objects.create(
            key="inactive_template",
            name="Inactive Template",
            subject="Test Subject",
            html_content="<p>Test</p>",
            text_content="Test",
            is_active=False,
        )

        cached_template = EmailTemplate.get_template("inactive_template")
        self.assertIsNone(cached_template)


class EmailServiceTestCase(TestCase):
    """Test EmailService functionality."""

    def setUp(self):
        """Set up test data."""
        self.user = User.objects.create_user(
            email="test@example.com", password="testpass123", name="Test User"
        )

        # Create test templates
        self.welcome_template = EmailTemplate.objects.create(
            key="welcome",
            name="Welcome Email",
            subject="Welcome {{user.name}}!",
            html_content="<h1>Welcome {{user.name}}!</h1><p>Email: {{user.email}}</p>",
            text_content="Welcome {{user.name}}! Your email: {{user.email}}",
            is_active=True,
        )

        self.notification_template = EmailTemplate.objects.create(
            key="notification",
            name="Notification Email",
            subject="{{title}}",
            html_content="<h1>{{title}}</h1><p>{{message}}</p>",
            text_content="{{title}}\n{{message}}",
            is_active=True,
        )

    def test_send_email_successfully(self):
        """Test successful email sending."""
        email_log = EmailService.send_email(
            template_key="welcome",
            to_email=self.user.email,
            context={"user": self.user},
            async_send=False,
        )

        # Check email log was created
        self.assertIsInstance(email_log, EmailMessageLog)
        self.assertEqual(email_log.to_email, self.user.email)
        self.assertEqual(email_log.template_key, "welcome")
        self.assertEqual(email_log.status, EmailStatus.SENT)

        # Check actual email was sent
        self.assertEqual(len(mail.outbox), 1)
        email = mail.outbox[0]
        self.assertEqual(email.to, [self.user.email])
        self.assertIn(self.user.name, email.subject)

    def test_send_email_nonexistent_template(self):
        """Test sending email with non-existent template."""
        with self.assertRaises(EmailTemplate.DoesNotExist):
            EmailService.send_email(
                template_key="nonexistent",
                to_email=self.user.email,
                context={"user": self.user},
                async_send=False,
            )

    def test_send_email_inactive_template(self):
        """Test sending email with inactive template."""
        EmailTemplate.objects.create(
            key="inactive",
            name="Inactive Template",
            subject="Test",
            html_content="<p>Test</p>",
            text_content="Test",
            is_active=False,
        )

        with self.assertRaises(ValueError):
            EmailService.send_email(
                template_key="inactive",
                to_email=self.user.email,
                context={"user": self.user},
                async_send=False,
            )

    def test_send_email_with_multiple_recipients(self):
        """Test sending email to multiple recipients."""
        recipients = ["user1@example.com", "user2@example.com"]

        email_log = EmailService.send_email(
            template_key="welcome",
            to_email=recipients,
            context={"user": self.user},
            async_send=False,
        )

        self.assertIsInstance(email_log, EmailMessageLog)
        self.assertEqual(email_log.to_email, "user1@example.com, user2@example.com")

    def test_send_bulk_email(self):
        """Test bulk email sending."""
        recipients = ["user1@example.com", "user2@example.com", "user3@example.com"]

        result = EmailService.send_bulk_email(
            template_key="welcome", recipients=recipients, context={"user": self.user}
        )

        self.assertEqual(result["total_sent"], 3)
        self.assertEqual(result["total_failed"], 0)
        self.assertEqual(len(result["failed_emails"]), 0)

    def test_email_preview(self):
        """Test email preview functionality."""
        preview = EmailService.preview_email(
            template_key="welcome", context={"user": self.user}
        )

        self.assertIn("subject", preview)
        self.assertIn("html_content", preview)
        self.assertIn("text_content", preview)
        self.assertIn(self.user.name, preview["subject"])

    @patch("apps.emails.services.EmailMultiAlternatives.send")
    def test_send_email_failure_handling(self, mock_send):
        """Test handling of email send failures."""
        mock_send.side_effect = Exception("SMTP Error")

        email_log = EmailService.send_email(
            template_key="welcome",
            to_email=self.user.email,
            context={"user": self.user},
            async_send=False,
        )

        # Check that email was marked as failed
        self.assertEqual(email_log.status, EmailStatus.FAILED)
        self.assertIn("SMTP Error", email_log.error_message)


class EmailMessageLogTestCase(TestCase):
    """Test EmailMessageLog model functionality."""

    def setUp(self):
        """Set up test data."""
        self.user = User.objects.create_user(
            email="test@example.com", password="testpass123", name="Test User"
        )

        self.template = EmailTemplate.objects.create(
            key="test_template",
            name="Test Template",
            subject="Test Subject",
            html_content="<p>Test</p>",
            text_content="Test",
            is_active=True,
        )

    def test_email_log_creation(self):
        """Test creating email log."""
        email_log = EmailMessageLog.objects.create(
            template=self.template,
            template_key=self.template.key,
            to_email="recipient@example.com",
            from_email="sender@example.com",
            subject="Test Subject",
            html_content="<p>Test content</p>",
            text_content="Test content",
            status=EmailStatus.PENDING,
            user=self.user,
        )

        self.assertEqual(email_log.to_email, "recipient@example.com")
        self.assertEqual(email_log.template, self.template)
        self.assertEqual(email_log.user, self.user)
        self.assertEqual(email_log.status, EmailStatus.PENDING)

    def test_email_log_status_methods(self):
        """Test email log status update methods."""
        email_log = EmailMessageLog.objects.create(
            template=self.template,
            template_key=self.template.key,
            to_email="recipient@example.com",
            from_email="sender@example.com",
            subject="Test Subject",
            html_content="<p>Test content</p>",
            text_content="Test content",
            status=EmailStatus.PENDING,
        )

        # Test mark as sent
        email_log.mark_as_sent()
        email_log.refresh_from_db()
        self.assertEqual(email_log.status, EmailStatus.SENT)
        self.assertIsNotNone(email_log.sent_at)

        # Test mark as failed
        email_log.mark_as_failed("Test error")
        email_log.refresh_from_db()
        self.assertEqual(email_log.status, EmailStatus.FAILED)
        self.assertEqual(email_log.error_message, "Test error")

    def test_cc_bcc_list_properties(self):
        """Test CC and BCC list properties."""
        email_log = EmailMessageLog.objects.create(
            template=self.template,
            template_key=self.template.key,
            to_email="recipient@example.com",
            from_email="sender@example.com",
            subject="Test Subject",
            html_content="<p>Test content</p>",
            text_content="Test content",
            status=EmailStatus.PENDING,
        )

        # Test CC list
        cc_emails = ["cc1@example.com", "cc2@example.com"]
        email_log.cc_list = cc_emails
        email_log.save()

        email_log.refresh_from_db()
        self.assertEqual(email_log.cc_list, cc_emails)

        # Test BCC list
        bcc_emails = ["bcc1@example.com", "bcc2@example.com"]
        email_log.bcc_list = bcc_emails
        email_log.save()

        email_log.refresh_from_db()
        self.assertEqual(email_log.bcc_list, bcc_emails)


class EmailTasksTestCase(TestCase):
    """Test email Celery tasks."""

    def setUp(self):
        """Set up test data."""
        self.user = User.objects.create_user(
            email="test@example.com", password="testpass123", name="Test User"
        )

        self.template = EmailTemplate.objects.create(
            key="test_template",
            name="Test Template",
            subject="Test Subject",
            html_content="<p>Test</p>",
            text_content="Test",
            is_active=True,
        )

    @patch("apps.emails.services.EmailService._send_email_now")
    def test_send_email_task_success(self, mock_send):
        """Test successful email task execution."""
        mock_send.return_value = True

        # Create email log
        email_log = EmailMessageLog.objects.create(
            template=self.template,
            template_key=self.template.key,
            to_email="recipient@example.com",
            from_email="sender@example.com",
            subject="Test Subject",
            html_content="<p>Test</p>",
            text_content="Test",
            status=EmailStatus.PENDING,
        )

        result = send_email_task(email_log.id)

        self.assertTrue(result["success"])
        self.assertEqual(result["email_log_id"], email_log.id)
        mock_send.assert_called_once_with(email_log)

    def test_send_email_task_nonexistent_log(self):
        """Test email task with non-existent log."""
        result = send_email_task(99999)

        self.assertFalse(result["success"])
        self.assertIn("not found", result["error"])

    @patch("apps.emails.services.EmailService.send_email")
    def test_send_bulk_email_task(self, mock_send):
        """Test bulk email task."""
        mock_send.return_value = Mock(status=EmailStatus.SENT)

        recipients = ["user1@example.com", "user2@example.com"]
        result = send_bulk_email_task("test_template", recipients, {"test": "context"})

        self.assertTrue(result["success"])
        self.assertEqual(result["sent_count"], 2)
        self.assertEqual(result["failed_count"], 0)
        self.assertEqual(mock_send.call_count, 2)

    def test_cleanup_old_email_logs(self):
        """Test cleanup of old email logs."""
        # Create old email log
        old_log = EmailMessageLog.objects.create(
            template=self.template,
            template_key=self.template.key,
            to_email="old@example.com",
            from_email="sender@example.com",
            subject="Old Email",
            html_content="<p>Old</p>",
            text_content="Old",
            status=EmailStatus.SENT,
        )
        old_log.created_at = timezone.now() - timedelta(days=35)
        old_log.save()

        # Create recent log
        recent_log = EmailMessageLog.objects.create(
            template=self.template,
            template_key=self.template.key,
            to_email="recent@example.com",
            from_email="sender@example.com",
            subject="Recent Email",
            html_content="<p>Recent</p>",
            text_content="Recent",
            status=EmailStatus.SENT,
        )

        result = cleanup_old_email_logs(30)

        self.assertTrue(result["success"])
        self.assertEqual(result["deleted_count"], 1)

        # Verify only recent log remains
        self.assertFalse(EmailMessageLog.objects.filter(id=old_log.id).exists())
        self.assertTrue(EmailMessageLog.objects.filter(id=recent_log.id).exists())


class EmailConvenienceFunctionsTestCase(TestCase):
    """Test email convenience functions."""

    def setUp(self):
        """Set up test data."""
        self.user = User.objects.create_user(
            email="test@example.com", password="testpass123", name="Test User"
        )

        # Create welcome template
        EmailTemplate.objects.create(
            key="welcome",
            name="Welcome Email",
            subject="Welcome {{user_name}}!",
            html_content=(
                "<h1>Welcome {{user_name}}!</h1>"
                "<p><a href='{{login_url}}'>Login</a></p>"
            ),
            text_content="Welcome {{user_name}}! Login at: {{login_url}}",
            is_active=True,
        )

        # Create password reset template
        EmailTemplate.objects.create(
            key="password_reset",
            name="Password Reset",
            subject="Password Reset for {{user_name}}",
            html_content="<p><a href='{{reset_link}}'>Reset Password</a></p>",
            text_content="Reset your password: {{reset_link}}",
            is_active=True,
        )

    @patch("apps.emails.services.EmailService.send_email")
    def test_send_welcome_email(self, mock_send):
        """Test welcome email convenience function."""
        mock_send.return_value = Mock()

        send_welcome_email(self.user)

        mock_send.assert_called_once()
        call_args = mock_send.call_args
        self.assertEqual(call_args[1]["template_key"], "welcome")
        self.assertEqual(call_args[1]["to_email"], self.user.email)
        self.assertIn("user", call_args[1]["context"])

    @patch("apps.emails.services.EmailService.send_email")
    def test_send_password_reset_email(self, mock_send):
        """Test password reset email convenience function."""
        mock_send.return_value = Mock()

        reset_link = "https://example.com/reset/token123"
        send_password_reset_email(self.user, reset_link)

        mock_send.assert_called_once()
        call_args = mock_send.call_args
        self.assertEqual(call_args[1]["template_key"], "password_reset")
        self.assertEqual(call_args[1]["to_email"], self.user.email)
        self.assertEqual(call_args[1]["context"]["reset_link"], reset_link)


@override_settings(CELERY_TASK_ALWAYS_EAGER=True)
class EmailIntegrationTestCase(TestCase):
    """Integration tests for complete email workflows."""

    def setUp(self):
        """Set up test data."""
        self.user = User.objects.create_user(
            email="test@example.com", password="testpass123", name="Test User"
        )

    def test_complete_email_workflow(self):
        """Test complete email workflow from template to delivery."""
        # 1. Create template
        template = EmailTemplate.objects.create(
            key="workflow_test",
            name="Workflow Test",
            subject="Hello {{user.name}}!",
            html_content="<h1>Hello {{user.name}}</h1><p>Email: {{user.email}}</p>",
            text_content="Hello {{user.name}}! Email: {{user.email}}",
            is_active=True,
        )

        # 2. Send email
        email_log = EmailService.send_email(
            template_key="workflow_test",
            to_email=self.user.email,
            context={"user": self.user},
            async_send=False,
        )

        # 3. Verify email log was created correctly
        self.assertEqual(email_log.template, template)
        self.assertEqual(email_log.to_email, self.user.email)
        self.assertEqual(email_log.status, EmailStatus.SENT)
        self.assertIsNotNone(email_log.sent_at)

        # 4. Verify actual email was sent
        self.assertEqual(len(mail.outbox), 1)
        email = mail.outbox[0]
        self.assertEqual(email.to, [self.user.email])
        self.assertEqual(email.subject, f"Hello {self.user.name}!")
        self.assertIn(self.user.name, email.body)
        self.assertIn(self.user.email, email.body)

        # 5. Verify HTML content
        self.assertEqual(len(email.alternatives), 1)
        html_content = email.alternatives[0][0]
        self.assertIn(f"<h1>Hello {self.user.name}</h1>", html_content)
        self.assertIn(self.user.email, html_content)

    def test_template_not_found_handling(self):
        """Test handling of missing templates."""
        with self.assertRaises(EmailTemplate.DoesNotExist):
            EmailService.send_email(
                template_key="nonexistent_template",
                to_email=self.user.email,
                context={"user": self.user},
                async_send=False,
            )

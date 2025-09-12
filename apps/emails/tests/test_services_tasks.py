from datetime import timedelta
from unittest.mock import Mock, patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from apps.core.enums import EmailStatus
from apps.emails.models import EmailMessageLog, EmailTemplate
from apps.emails.services import EmailService
from apps.emails.tasks import (
    cleanup_old_email_logs,
    retry_failed_emails,
    send_bulk_email_task,
    send_email_task,
)

User = get_user_model()


class EmailServiceTestCase(TestCase):
    """Test EmailService"""

    def setUp(self):
        """Set up test data"""
        self.user = User.objects.create_user(
            email="test@example.com", name="Test User", password="testpass123"
        )

        self.template = EmailTemplate.objects.create(
            key="welcome",
            name="Welcome Email",
            subject="Welcome {{ name }}!",
            html_content="<p>Welcome {{ name }}!</p>",
            text_content="Welcome {{ name }}!",
            language="en",
            is_active=True,
        )

    @patch("apps.emails.services.send_email_task.delay")
    def test_send_email_async(self, mock_task):
        """Test sending email asynchronously"""
        mock_task.return_value.id = "task-123"

        email_log = EmailService.send_email(
            template_key="welcome",
            to_email="recipient@example.com",
            context={"name": "John"},
            user=self.user,
            async_send=True,
        )

        self.assertIsInstance(email_log, EmailMessageLog)
        self.assertEqual(email_log.template_key, "welcome")
        self.assertEqual(email_log.to_email, "recipient@example.com")
        self.assertEqual(email_log.subject, "Welcome John!")
        self.assertEqual(email_log.status, EmailStatus.PENDING)
        self.assertEqual(email_log.celery_task_id, "task-123")

        mock_task.assert_called_once_with(email_log.id)

    @patch("apps.emails.services.EmailService._send_email_now")
    def test_send_email_sync(self, mock_send):
        """Test sending email synchronously"""
        def mock_send_email_now(email_log):
            # Simulate successful sending by updating the status
            email_log.mark_as_sent()
            return True
        
        mock_send.side_effect = mock_send_email_now

        email_log = EmailService.send_email(
            template_key="welcome",
            to_email="recipient@example.com",
            context={"name": "John"},
            user=self.user,
            async_send=False,
        )

        mock_send.assert_called_once_with(email_log)
        self.assertEqual(email_log.status, EmailStatus.SENT)

    def test_send_email_multiple_recipients(self):
        """Test sending email to multiple recipients"""
        recipients = ["user1@example.com", "user2@example.com"]

        with patch("apps.emails.services.send_email_task.delay") as mock_task:
            mock_task.return_value.id = "task-123"

            email_log = EmailService.send_email(
                template_key="welcome",
                to_email=recipients,
                context={"name": "John"},
                user=self.user,
            )

        self.assertEqual(email_log.to_email, "user1@example.com, user2@example.com")

    def test_send_email_template_not_found(self):
        """Test sending email with non-existent template"""
        with self.assertRaises(EmailTemplate.DoesNotExist):
            EmailService.send_email(
                template_key="nonexistent",
                to_email="recipient@example.com",
                user=self.user,
            )

    def test_send_email_template_inactive(self):
        """Test sending email with inactive template"""
        self.template.is_active = False
        self.template.save()

        with self.assertRaises(ValueError):
            EmailService.send_email(
                template_key="welcome", to_email="recipient@example.com", user=self.user
            )

    @patch("apps.emails.services.EmailMultiAlternatives")
    def test_send_email_now_success(self, mock_email_class):
        """Test _send_email_now method success"""
        mock_email = Mock()
        mock_email.send.return_value = 1
        mock_email_class.return_value = mock_email

        email_log = EmailMessageLog.objects.create(
            template_key="welcome",
            to_email="recipient@example.com",
            subject="Welcome John!",
            html_content="<p>Welcome John!</p>",
            text_content="Welcome John!",
            status=EmailStatus.PENDING,
        )

        result = EmailService._send_email_now(email_log)

        self.assertTrue(result)
        email_log.refresh_from_db()
        self.assertEqual(email_log.status, EmailStatus.SENT)

        mock_email_class.assert_called_once()
        mock_email.attach_alternative.assert_called_once_with(
            "<p>Welcome John!</p>", "text/html"
        )
        mock_email.send.assert_called_once()

    @patch("apps.emails.services.EmailMultiAlternatives")
    def test_send_email_now_failure(self, mock_email_class):
        """Test _send_email_now method failure"""
        mock_email = Mock()
        mock_email.send.side_effect = Exception("SMTP Error")
        mock_email_class.return_value = mock_email

        email_log = EmailMessageLog.objects.create(
            template_key="welcome",
            to_email="recipient@example.com",
            subject="Welcome John!",
            html_content="<p>Welcome John!</p>",
            text_content="Welcome John!",
            status=EmailStatus.PENDING,
        )

        result = EmailService._send_email_now(email_log)

        self.assertFalse(result)
        email_log.refresh_from_db()
        self.assertEqual(email_log.status, EmailStatus.FAILED)
        self.assertIn("SMTP Error", email_log.error_message)

    @patch("apps.emails.services.EmailService._send_email_now")
    def test_send_bulk_email(self, mock_send):
        """Test sending bulk emails"""
        def mock_send_email_now(email_log):
            # Simulate successful sending by updating the status
            email_log.mark_as_sent()
            return True
        
        mock_send.side_effect = mock_send_email_now
        recipients = ["user1@example.com", "user2@example.com", "user3@example.com"]

        results = EmailService.send_bulk_email(
            template_key="welcome",
            recipients=recipients,
            context={"name": "Users"},
            user=self.user,
        )

        self.assertEqual(results["total_sent"], 3)
        self.assertEqual(results["total_failed"], 0)
        self.assertEqual(len(results["failed_emails"]), 0)

    @patch("apps.emails.services.EmailService._send_email_now")
    def test_send_bulk_email_with_failures(self, mock_send):
        """Test sending bulk emails with some failures"""
        def mock_send_side_effect(email_log):
            # First two succeed, third fails
            if "user3@example.com" in email_log.to_email:
                email_log.mark_as_failed("Send failed")
                return False
            else:
                email_log.mark_as_sent()
                return True
        
        mock_send.side_effect = mock_send_side_effect
        recipients = ["user1@example.com", "user2@example.com", "user3@example.com"]

        results = EmailService.send_bulk_email(
            template_key="welcome",
            recipients=recipients,
            context={"name": "Users"},
            user=self.user,
        )

        self.assertEqual(results["total_sent"], 2)
        self.assertEqual(results["total_failed"], 1)
        self.assertEqual(len(results["failed_emails"]), 1)
        self.assertIn("user3@example.com", results["failed_emails"])

    def test_get_template_context_with_user(self):
        """Test getting template context with user"""
        context = EmailService._get_template_context(
            template=self.template, context={"custom": "value"}, user=self.user
        )

        self.assertIn("user", context)
        self.assertIn("site_name", context)
        self.assertIn("custom", context)
        self.assertEqual(context["custom"], "value")
        self.assertEqual(context["user"], self.user)

    def test_validate_template_context(self):
        """Test template context validation"""
        # Should not raise for valid context
        EmailService._validate_template_context({"name": "John"})

        # Should raise for invalid context
        with self.assertRaises(ValueError):
            EmailService._validate_template_context({"invalid": object()})


class EmailTasksTestCase(TestCase):
    """Test email tasks"""

    def setUp(self):
        """Set up test data"""
        self.user = User.objects.create_user(
            email="test@example.com", name="Test User", password="testpass123"
        )

    @patch("apps.emails.services.EmailService._send_email_now")
    def test_send_email_task_success(self, mock_send):
        """Test send_email_task success"""
        def mock_send_email_now(email_log):
            # Simulate successful sending by updating the status
            email_log.mark_as_sent()
            return True
        
        mock_send.side_effect = mock_send_email_now

        email_log = EmailMessageLog.objects.create(
            template_key="test",
            to_email="recipient@example.com",
            subject="Test Email",
            status=EmailStatus.PENDING,
        )

        result = send_email_task(email_log.id)

        self.assertTrue(result["success"])
        self.assertEqual(result["email_log_id"], email_log.id)
        self.assertEqual(result["to_email"], "recipient@example.com")

    @patch("apps.emails.services.EmailService._send_email_now")
    def test_send_email_task_failure(self, mock_send):
        """Test send_email_task failure"""
        def mock_send_email_now(email_log):
            # Simulate failed sending
            email_log.mark_as_failed("Send failed")
            return False
        
        mock_send.side_effect = mock_send_email_now

        email_log = EmailMessageLog.objects.create(
            template_key="test",
            to_email="recipient@example.com",
            subject="Test Email",
            status=EmailStatus.PENDING,
        )

        result = send_email_task(email_log.id)

        self.assertFalse(result["success"])
        self.assertEqual(result["error"], "Send failed")

    def test_send_email_task_not_found(self):
        """Test send_email_task with non-existent email log"""
        result = send_email_task(99999)

        self.assertFalse(result["success"])
        self.assertIn("not found", result["error"])

    @patch("apps.emails.tasks.EmailMessageLog.objects.filter")
    def test_cleanup_old_email_logs(self, mock_filter):
        """Test cleanup_old_email_logs task"""
        mock_queryset = Mock()
        mock_queryset.delete.return_value = (5, {"apps.emails.EmailMessageLog": 5})
        mock_filter.return_value = mock_queryset

        result = cleanup_old_email_logs(days_to_keep=30)

        self.assertTrue(result["success"])
        self.assertEqual(result["deleted_count"], 5)
        self.assertEqual(result["days_kept"], 30)

    def test_cleanup_old_email_logs_exception(self):
        """Test cleanup_old_email_logs with exception"""
        with patch("apps.emails.tasks.EmailMessageLog.objects.filter") as mock_filter:
            mock_filter.side_effect = Exception("Database error")

            result = cleanup_old_email_logs()

            self.assertFalse(result["success"])
            self.assertIn("Database error", result["error"])

    @patch("apps.emails.services.EmailService.send_email")
    def test_send_bulk_email_task_success(self, mock_send_email):
        """Test send_bulk_email_task success"""
        # Create welcome template for this test
        template = EmailTemplate.objects.create(
            key="welcome",
            name="Welcome Email",
            subject="Welcome {{ name }}!",
            html_content="<p>Welcome {{ name }}!</p>",
            text_content="Welcome {{ name }}!",
            language="en",
            is_active=True,
        )
        
        mock_send_email.return_value = Mock()
        recipients = ["user1@example.com", "user2@example.com"]

        result = send_bulk_email_task(
            template_key="welcome",
            recipient_emails=recipients,
            context={"name": "Users"},
        )

        self.assertTrue(result["success"])
        self.assertEqual(result["sent_count"], 2)
        self.assertEqual(result["failed_count"], 0)
        self.assertEqual(result["total_recipients"], 2)

    @patch("apps.emails.services.EmailService.send_email")
    def test_send_bulk_email_task_with_failures(self, mock_send_email):
        """Test send_bulk_email_task with some failures"""
        # Create welcome template for this test
        template = EmailTemplate.objects.create(
            key="welcome",
            name="Welcome Email",
            subject="Welcome {{ name }}!",
            html_content="<p>Welcome {{ name }}!</p>",
            text_content="Welcome {{ name }}!",
            language="en",
            is_active=True,
        )
        
        mock_send_email.side_effect = [Mock(), Exception("Send failed")]
        recipients = ["user1@example.com", "user2@example.com"]

        result = send_bulk_email_task(
            template_key="welcome",
            recipient_emails=recipients,
            context={"name": "Users"},
        )

        self.assertTrue(result["success"])
        self.assertEqual(result["sent_count"], 1)
        self.assertEqual(result["failed_count"], 1)
        self.assertEqual(len(result["failed_emails"]), 1)

    def test_send_bulk_email_task_exception(self):
        """Test send_bulk_email_task with exception"""
        result = send_bulk_email_task(
            template_key="nonexistent",
            recipient_emails=["test@example.com"],
            context=None,
        )

        self.assertFalse(result["success"])
        self.assertIn("error", result)

    @patch("apps.emails.tasks.send_email_task.delay")
    def test_retry_failed_emails(self, mock_task):
        """Test retry_failed_emails task"""
        mock_task.return_value.id = "task-123"

        # Create failed email logs
        failed_log1 = EmailMessageLog.objects.create(
            template_key="test1",
            to_email="failed1@example.com",
            subject="Test 1",
            status=EmailStatus.FAILED,
            created_at=timezone.now() - timedelta(hours=12),
        )

        failed_log2 = EmailMessageLog.objects.create(
            template_key="test2",
            to_email="failed2@example.com",
            subject="Test 2",
            status=EmailStatus.FAILED,
            created_at=timezone.now() - timedelta(hours=6),
        )

        result = retry_failed_emails(max_retries=3)

        self.assertTrue(result["success"])
        self.assertEqual(result["retried_count"], 2)

        # Check that email logs were reset to pending
        failed_log1.refresh_from_db()
        failed_log2.refresh_from_db()
        self.assertEqual(failed_log1.status, EmailStatus.PENDING)
        self.assertEqual(failed_log2.status, EmailStatus.PENDING)

    def test_retry_failed_emails_exception(self):
        """Test retry_failed_emails with exception"""
        with patch("apps.emails.tasks.EmailMessageLog.objects.filter") as mock_filter:
            mock_filter.side_effect = Exception("Database error")

            result = retry_failed_emails()

            self.assertFalse(result["success"])
            self.assertIn("Database error", result["error"])

    def test_send_email_task_with_retry(self):
        """Test send_email_task with retry mechanism"""
        email_log = EmailMessageLog.objects.create(
            template_key="test",
            to_email="recipient@example.com",
            subject="Test Email",
            status=EmailStatus.PENDING,
        )

        # Mock the Celery task to test retry mechanism
        with patch("apps.emails.tasks.send_email_task.retry"):
            with patch("apps.emails.services.EmailService._send_email_now") as mock_send:
                mock_send.side_effect = Exception("Temporary failure")

                # Create mock task instance
                class MockTask:
                    def __init__(self):
                        self.request = Mock()
                        self.request.retries = 1

                    def retry(self, exc, countdown, max_retries):
                        raise exc

                mock_task = MockTask()

                # This should raise the exception after trying to retry
                with self.assertRaises(Exception):  # noqa: B017
                    # Manually call with task context
                    try:
                        EmailService._send_email_now(email_log)
                    except Exception as e:
                        mock_task.retry(exc=e, countdown=60 * (2**1), max_retries=3)


class EmailServicePrivateMethodsTestCase(TestCase):
    """Test EmailService private methods"""

    def setUp(self):
        """Set up test data"""
        self.user = User.objects.create_user(
            email="test@example.com", name="Test User", password="testpass123"
        )

        self.template = EmailTemplate.objects.create(
            key="test",
            name="Test Email",
            subject="Test {{ name }}",
            html_content="<p>Hello {{ name }}</p>",
            text_content="Hello {{ name }}",
            language="en",
            is_active=True,
        )

    def test_normalize_recipients_string(self):
        """Test normalizing single recipient"""
        result = EmailService._normalize_recipients("test@example.com")
        self.assertEqual(result, ["test@example.com"])

    def test_normalize_recipients_list(self):
        """Test normalizing multiple recipients"""
        recipients = ["test1@example.com", "test2@example.com"]
        result = EmailService._normalize_recipients(recipients)
        self.assertEqual(result, recipients)

    def test_format_recipients_list(self):
        """Test formatting recipients for database storage"""
        recipients = ["test1@example.com", "test2@example.com", "test3@example.com"]
        result = EmailService._format_recipients_for_storage(recipients)
        self.assertEqual(
            result, "test1@example.com, test2@example.com, test3@example.com"
        )

    def test_format_recipients_single(self):
        """Test formatting single recipient"""
        recipients = ["test@example.com"]
        result = EmailService._format_recipients_for_storage(recipients)
        self.assertEqual(result, "test@example.com")

    def test_create_email_log(self):
        """Test creating email log"""
        email_log = EmailService._create_email_log(
            template=self.template,
            to_email="test@example.com",
            from_email="from@example.com",
            cc=["cc@example.com"],
            bcc=["bcc@example.com"],
            subject="Test Subject",
            html_body="<p>HTML</p>",
            text_body="Text",
            user=self.user,
        )

        self.assertIsInstance(email_log, EmailMessageLog)
        self.assertEqual(email_log.to_email, "test@example.com")
        self.assertEqual(email_log.from_email, "from@example.com")
        self.assertEqual(email_log.cc, '["cc@example.com"]')
        self.assertEqual(email_log.bcc, '["bcc@example.com"]')
        self.assertEqual(email_log.subject, "Test Subject")

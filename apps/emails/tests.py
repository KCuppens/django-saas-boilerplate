import json
from datetime import timedelta
from unittest.mock import Mock, patch

import pytest
from celery.exceptions import Retry
from django.contrib.auth import get_user_model
from django.core import mail
from django.core.cache import cache
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from apps.core.enums import EmailStatus
from apps.emails.models import EmailMessageLog, EmailTemplate
from apps.emails.services import (
    EmailService,
    send_notification_email,
    send_password_reset_email,
    send_welcome_email,
)
from apps.emails.tasks import (
    cleanup_old_email_logs,
    retry_failed_emails,
    send_bulk_email_task,
    send_email_task,
)

User = get_user_model()


# Test Fixtures and Utilities
@pytest.fixture
def user():
    """Create a test user"""
    return User.objects.create_user(
        email="test@example.com",
        password="testpass123",
        name="Test User"
    )


@pytest.fixture
def admin_user():
    """Create an admin user"""
    return User.objects.create_user(
        email="admin@example.com",
        password="adminpass123",
        name="Admin User",
        is_staff=True,
        is_superuser=True,
    )


@pytest.fixture
def email_template():
    """Create a test email template"""
    return EmailTemplate.objects.create(
        key="test-template",
        name="Test Template",
        description="A test email template",
        subject="Test Subject: {{ title }}",
        html_content="<h1>{{ title }}</h1><p>Hello {{ user_name }}!</p>",
        text_content="{{ title }}\nHello {{ user_name }}!",
        is_active=True,
        category="test",
        language="en",
        template_variables={
            "title": "string",
            "user_name": "string"
        }
    )


@pytest.fixture
def welcome_template():
    """Create a welcome email template"""
    return EmailTemplate.objects.create(
        key="welcome",
        name="Welcome Email",
        description="Welcome new users",
        subject="Welcome to our platform, {{ user_name }}!",
        html_content="""
        <h1>Welcome {{ user_name }}!</h1>
        <p>Thanks for joining us.</p>
        <a href="{{ login_url }}">Login here</a>
        """,
        text_content="Welcome {{ user_name }}!\nThanks for joining us.\nLogin: {{ login_url }}",
        is_active=True,
        category="auth",
        language="en"
    )


@pytest.fixture
def email_log(user, email_template):
    """Create a test email log"""
    return EmailMessageLog.objects.create(
        template=email_template,
        template_key=email_template.key,
        to_email="recipient@example.com",
        from_email="sender@example.com",
        subject="Test Email",
        html_content="<p>Test content</p>",
        text_content="Test content",
        status=EmailStatus.PENDING,
        context_data={"test": "data"},
        user=user
    )


@pytest.fixture
def celery_eager(settings):
    """Configure Celery to execute tasks synchronously"""
    settings.CELERY_TASK_ALWAYS_EAGER = True
    settings.CELERY_TASK_EAGER_PROPAGATES = True


@pytest.fixture
def clear_cache():
    """Clear cache before and after tests"""
    cache.clear()
    yield
    cache.clear()


class EmailTemplateModelTest(TestCase):
    """Test EmailTemplate model functionality"""

    def setUp(self):
        self.template = EmailTemplate.objects.create(
            key="test-template",
            name="Test Template",
            subject="Hello {{ user_name }}",
            html_content="<h1>{{ title }}</h1><p>Hello {{ user_name }}!</p>",
            text_content="{{ title }}\nHello {{ user_name }}!",
            is_active=True,
            template_variables={"user_name": "string", "title": "string"}
        )

    def test_string_representation(self):
        """Test template string representation"""
        expected = "Test Template (test-template)"
        self.assertEqual(str(self.template), expected)

    def test_cache_key_property(self):
        """Test cache key generation"""
        expected = "email_template:test-template:en"
        self.assertEqual(self.template.cache_key, expected)

    def test_render_subject(self):
        """Test subject rendering with context"""
        context = {"user_name": "John Doe"}
        rendered = self.template.render_subject(context)
        self.assertEqual(rendered, "Hello John Doe")

    def test_render_html(self):
        """Test HTML content rendering with context"""
        context = {"title": "Welcome", "user_name": "John Doe"}
        rendered = self.template.render_html(context)
        self.assertIn("<h1>Welcome</h1>", rendered)
        self.assertIn("Hello John Doe!", rendered)

    def test_render_text(self):
        """Test text content rendering with context"""
        context = {"title": "Welcome", "user_name": "John Doe"}
        rendered = self.template.render_text(context)
        self.assertIn("Welcome", rendered)
        self.assertIn("Hello John Doe!", rendered)

    def test_render_all(self):
        """Test rendering all parts of email"""
        context = {"title": "Welcome", "user_name": "John Doe"}
        rendered = self.template.render_all(context)

        self.assertIn("subject", rendered)
        self.assertIn("html_content", rendered)
        self.assertIn("text_content", rendered)
        self.assertEqual(rendered["subject"], "Hello John Doe")
        self.assertIn("Welcome", rendered["html_content"])
        self.assertIn("John Doe", rendered["text_content"])

    def test_render_with_empty_context(self):
        """Test rendering with empty context"""
        rendered = self.template.render_all({})
        self.assertEqual(rendered["subject"], "Hello ")

    @patch('django.core.cache.cache.delete')
    def test_save_clears_cache(self, mock_cache_delete):
        """Test that saving template clears relevant cache"""
        self.template.save()

        # Should call cache.delete twice - once for specific template, once for general
        self.assertEqual(mock_cache_delete.call_count, 2)
        mock_cache_delete.assert_any_call(self.template.cache_key)
        mock_cache_delete.assert_any_call(f"email_templates:{self.template.key}")

    def test_get_template_with_cache(self):
        """Test template retrieval with caching"""
        # Clear cache first
        cache.clear()

        # First call should fetch from database
        template1 = EmailTemplate.get_template("test-template")
        self.assertEqual(template1.key, "test-template")

        # Second call should fetch from cache
        with patch.object(EmailTemplate.objects, 'get') as mock_get:
            template2 = EmailTemplate.get_template("test-template")
            self.assertEqual(template2.key, "test-template")
            mock_get.assert_not_called()  # Should not hit database

    def test_get_template_not_found(self):
        """Test template retrieval for non-existent template"""
        template = EmailTemplate.get_template("non-existent")
        self.assertIsNone(template)

    def test_get_template_fallback_to_english(self):
        """Test template language fallback to English"""
        # Template should fallback to English if requested language not found
        template = EmailTemplate.get_template("test-template", "fr")
        self.assertEqual(template.language, "en")
        self.assertEqual(template.key, "test-template")

    def test_get_template_inactive(self):
        """Test that inactive templates are not returned"""
        self.template.is_active = False
        self.template.save()

        template = EmailTemplate.get_template("test-template")
        self.assertIsNone(template)

    def test_unique_together_constraint(self):
        """Test unique_together constraint for key and language"""
        from django.db import IntegrityError

        with self.assertRaises(IntegrityError):
            EmailTemplate.objects.create(
                key="test-template",  # Same key
                language="en",        # Same language
                name="Duplicate Template",
                subject="Test",
                html_content="<p>Test</p>",
                text_content="Test"
            )


class EmailMessageLogModelTest(TestCase):
    """Test EmailMessageLog model functionality"""

    def setUp(self):
        self.user = User.objects.create_user(
            email="test@example.com",
            password="testpass123"
        )

        self.template = EmailTemplate.objects.create(
            key="test-template",
            name="Test Template",
            subject="Test",
            html_content="<p>Test</p>",
            text_content="Test"
        )

        self.email_log = EmailMessageLog.objects.create(
            template=self.template,
            template_key="test-template",
            to_email="recipient@example.com",
            from_email="sender@example.com",
            subject="Test Email",
            html_content="<p>Test content</p>",
            text_content="Test content",
            cc='["cc@example.com"]',
            bcc='["bcc@example.com"]',
            context_data={"test": "value"},
            user=self.user
        )

    def test_string_representation(self):
        """Test email log string representation"""
        expected = "Email to recipient@example.com - Test Email"
        self.assertEqual(str(self.email_log), expected)

    def test_cc_list_property(self):
        """Test CC list property getter"""
        cc_list = self.email_log.cc_list
        self.assertEqual(cc_list, ["cc@example.com"])

    def test_cc_list_setter(self):
        """Test CC list property setter"""
        self.email_log.cc_list = ["new@example.com", "another@example.com"]
        self.assertEqual(self.email_log.cc, '["new@example.com", "another@example.com"]')

    def test_bcc_list_property(self):
        """Test BCC list property getter"""
        bcc_list = self.email_log.bcc_list
        self.assertEqual(bcc_list, ["bcc@example.com"])

    def test_bcc_list_setter(self):
        """Test BCC list property setter"""
        self.email_log.bcc_list = ["secret@example.com"]
        self.assertEqual(self.email_log.bcc, '["secret@example.com"]')

    def test_cc_list_empty(self):
        """Test CC list when empty"""
        self.email_log.cc = ""
        self.assertEqual(self.email_log.cc_list, [])

    def test_bcc_list_empty(self):
        """Test BCC list when empty"""
        self.email_log.bcc = ""
        self.assertEqual(self.email_log.bcc_list, [])

    def test_cc_list_invalid_json(self):
        """Test CC list with invalid JSON"""
        self.email_log.cc = "invalid json"
        self.assertEqual(self.email_log.cc_list, [])

    def test_bcc_list_invalid_json(self):
        """Test BCC list with invalid JSON"""
        self.email_log.bcc = "invalid json"
        self.assertEqual(self.email_log.bcc_list, [])

    def test_mark_as_sent(self):
        """Test marking email as sent"""
        with patch('django.utils.timezone.now') as mock_now:
            mock_time = timezone.now()
            mock_now.return_value = mock_time

            self.email_log.mark_as_sent()

            self.assertEqual(self.email_log.status, EmailStatus.SENT)
            self.assertEqual(self.email_log.sent_at, mock_time)

    def test_mark_as_failed(self):
        """Test marking email as failed"""
        error_message = "SMTP connection failed"
        self.email_log.mark_as_failed(error_message)

        self.assertEqual(self.email_log.status, EmailStatus.FAILED)
        self.assertEqual(self.email_log.error_message, error_message)

    def test_mark_as_delivered(self):
        """Test marking email as delivered"""
        with patch('django.utils.timezone.now') as mock_now:
            mock_time = timezone.now()
            mock_now.return_value = mock_time

            self.email_log.mark_as_delivered()

            self.assertEqual(self.email_log.status, EmailStatus.DELIVERED)
            self.assertEqual(self.email_log.delivered_at, mock_time)

    def test_mark_as_opened(self):
        """Test marking email as opened"""
        with patch('django.utils.timezone.now') as mock_now:
            mock_time = timezone.now()
            mock_now.return_value = mock_time

            self.email_log.mark_as_opened()

            self.assertEqual(self.email_log.status, EmailStatus.OPENED)
            self.assertEqual(self.email_log.opened_at, mock_time)

    def test_mark_as_clicked(self):
        """Test marking email as clicked"""
        with patch('django.utils.timezone.now') as mock_now:
            mock_time = timezone.now()
            mock_now.return_value = mock_time

            self.email_log.mark_as_clicked()

            self.assertEqual(self.email_log.status, EmailStatus.CLICKED)
            self.assertEqual(self.email_log.clicked_at, mock_time)


class EmailServiceTest(TestCase):
    """Test EmailService functionality"""

    def setUp(self):
        self.user = User.objects.create_user(
            email="test@example.com",
            password="testpass123",
            name="Test User"
        )

        self.template = EmailTemplate.objects.create(
            key="test-template",
            name="Test Template",
            subject="Hello {{ user_name }}",
            html_content="<h1>{{ title }}</h1><p>Hello {{ user_name }}!</p>",
            text_content="{{ title }}\nHello {{ user_name }}!",
            is_active=True
        )

    @override_settings(DEFAULT_FROM_EMAIL="default@example.com")
    def test_send_email_basic(self):
        """Test basic email sending"""
        with patch('apps.emails.tasks.send_email_task.delay') as mock_delay:
            mock_task = Mock()
            mock_task.id = "task-123"
            mock_delay.return_value = mock_task

            email_log = EmailService.send_email(
                template_key="test-template",
                to_email="recipient@example.com",
                context={"user_name": "John", "title": "Welcome"},
                user=self.user
            )

            # Check email log was created
            self.assertEqual(email_log.to_email, "recipient@example.com")
            self.assertEqual(email_log.from_email, "default@example.com")
            self.assertEqual(email_log.subject, "Hello John")
            self.assertIn("Welcome", email_log.html_content)
            self.assertEqual(email_log.template_key, "test-template")
            self.assertEqual(email_log.user, self.user)
            self.assertEqual(email_log.celery_task_id, "task-123")

            # Check task was scheduled
            mock_delay.assert_called_once_with(email_log.id)

    def test_send_email_template_not_found(self):
        """Test sending email with non-existent template"""
        with self.assertRaises(ValueError) as context:
            EmailService.send_email(
                template_key="non-existent",
                to_email="recipient@example.com"
            )

        self.assertIn("Email template 'non-existent' not found", str(context.exception))

    def test_send_email_template_render_error(self):
        """Test handling template rendering errors"""
        # Create template with invalid syntax
        EmailTemplate.objects.create(
            key="bad-template",
            name="Bad Template",
            subject="{{ invalid | unknown_filter }}",
            html_content="<p>Test</p>",
            text_content="Test"
        )

        with self.assertRaises(ValueError) as context:
            EmailService.send_email(
                template_key="bad-template",
                to_email="recipient@example.com"
            )

        self.assertIn("Failed to render email template", str(context.exception))

    @patch('apps.emails.services.EmailService._send_email_now')
    def test_send_email_synchronous(self, mock_send_now):
        """Test synchronous email sending"""
        mock_send_now.return_value = True

        email_log = EmailService.send_email(
            template_key="test-template",
            to_email="recipient@example.com",
            context={"user_name": "John", "title": "Welcome"},
            async_send=False
        )

        mock_send_now.assert_called_once_with(email_log)
        self.assertEqual(email_log.celery_task_id, "")

    def test_send_email_with_cc_bcc(self):
        """Test sending email with CC and BCC"""
        email_log = EmailService.send_email(
            template_key="test-template",
            to_email="recipient@example.com",
            cc=["cc@example.com"],
            bcc=["bcc@example.com"],
            context={"user_name": "John", "title": "Welcome"},
            async_send=False
        )

        self.assertEqual(email_log.cc_list, ["cc@example.com"])
        self.assertEqual(email_log.bcc_list, ["bcc@example.com"])

    def test_send_email_list_recipients(self):
        """Test sending email to multiple recipients (first one used)"""
        email_log = EmailService.send_email(
            template_key="test-template",
            to_email=["first@example.com", "second@example.com"],
            context={"user_name": "John", "title": "Welcome"},
            async_send=False
        )

        # Should use first recipient
        self.assertEqual(email_log.to_email, "first@example.com")

    @patch('django.core.mail.EmailMultiAlternatives')
    def test_send_email_now_success(self, mock_email_class):
        """Test successful immediate email sending"""
        mock_email = Mock()
        mock_email_class.return_value = mock_email

        email_log = EmailMessageLog.objects.create(
            template=self.template,
            template_key="test-template",
            to_email="recipient@example.com",
            from_email="sender@example.com",
            subject="Test Email",
            html_content="<p>Test content</p>",
            text_content="Test content",
            cc='["cc@example.com"]',
            bcc='["bcc@example.com"]'
        )

        result = EmailService._send_email_now(email_log)

        # Check email was created correctly
        mock_email_class.assert_called_once_with(
            subject="Test Email",
            body="Test content",
            from_email="sender@example.com",
            to=["recipient@example.com"],
            cc=["cc@example.com"],
            bcc=["bcc@example.com"]
        )

        # Check HTML alternative was attached
        mock_email.attach_alternative.assert_called_once_with("<p>Test content</p>", "text/html")

        # Check email was sent
        mock_email.send.assert_called_once_with(fail_silently=False)

        # Check result and email log status
        self.assertTrue(result)
        email_log.refresh_from_db()
        self.assertEqual(email_log.status, EmailStatus.SENT)
        self.assertIsNotNone(email_log.sent_at)

    @patch('django.core.mail.EmailMultiAlternatives')
    def test_send_email_now_failure(self, mock_email_class):
        """Test failed immediate email sending"""
        mock_email = Mock()
        mock_email.send.side_effect = Exception("SMTP Error")
        mock_email_class.return_value = mock_email

        email_log = EmailMessageLog.objects.create(
            template=self.template,
            template_key="test-template",
            to_email="recipient@example.com",
            from_email="sender@example.com",
            subject="Test Email",
            html_content="<p>Test content</p>",
            text_content="Test content"
        )

        result = EmailService._send_email_now(email_log)

        # Check result and email log status
        self.assertFalse(result)
        email_log.refresh_from_db()
        self.assertEqual(email_log.status, EmailStatus.FAILED)
        self.assertEqual(email_log.error_message, "SMTP Error")

    def test_send_template_email(self):
        """Test convenience method for sending template emails"""
        with patch.object(EmailService, 'send_email') as mock_send:
            mock_send.return_value = Mock()

            EmailService.send_template_email(
                template_key="test-template",
                to_email="recipient@example.com",
                context={"user_name": "John"}
            )

            mock_send.assert_called_once_with(
                template_key="test-template",
                to_email="recipient@example.com",
                context={"user_name": "John"}
            )

    def test_send_bulk_email(self):
        """Test bulk email sending"""
        recipients = ["user1@example.com", "user2@example.com", "user3@example.com"]

        with patch.object(EmailService, 'send_email') as mock_send:
            mock_send.side_effect = [Mock(), Mock(), Exception("Failed")]

            email_logs = EmailService.send_bulk_email(
                template_key="test-template",
                recipients=recipients,
                context={"title": "Bulk Email"}
            )

            # Should have 2 successful logs (third failed)
            self.assertEqual(len(email_logs), 2)
            self.assertEqual(mock_send.call_count, 3)

    def test_preview_email(self):
        """Test email preview functionality"""
        preview = EmailService.preview_email(
            template_key="test-template",
            context={"user_name": "John", "title": "Preview"}
        )

        self.assertIn("subject", preview)
        self.assertIn("html_content", preview)
        self.assertIn("text_content", preview)
        self.assertEqual(preview["subject"], "Hello John")
        self.assertIn("Preview", preview["html_content"])

    def test_preview_email_template_not_found(self):
        """Test preview with non-existent template"""
        with self.assertRaises(ValueError) as context:
            EmailService.preview_email(template_key="non-existent")

        self.assertIn("Email template 'non-existent' not found", str(context.exception))


class EmailConvenienceFunctionsTest(TestCase):
    """Test convenience functions for common email types"""

    def setUp(self):
        self.user = User.objects.create_user(
            email="test@example.com",
            password="testpass123",
            name="John Doe"
        )

        # Create welcome template
        EmailTemplate.objects.create(
            key="welcome",
            name="Welcome Email",
            subject="Welcome {{ user_name }}!",
            html_content="<h1>Welcome {{ user_name }}!</h1><p><a href='{{ login_url }}'>Login</a></p>",
            text_content="Welcome {{ user_name }}!\nLogin: {{ login_url }}",
            is_active=True
        )

        # Create password reset template
        EmailTemplate.objects.create(
            key="password_reset",
            name="Password Reset",
            subject="Reset your password",
            html_content="<p>Hi {{ user_name }}, <a href='{{ reset_link }}'>Reset password</a></p>",
            text_content="Hi {{ user_name }}, reset: {{ reset_link }}",
            is_active=True
        )

        # Create notification template
        EmailTemplate.objects.create(
            key="notification",
            name="Notification Email",
            subject="{{ title }}",
            html_content="<h2>{{ title }}</h2><p>{{ message }}</p>",
            text_content="{{ title }}\n{{ message }}",
            is_active=True
        )

    @patch.object(EmailService, 'send_email')
    @override_settings(LOGIN_URL="/custom/login/")
    def test_send_welcome_email(self, mock_send):
        """Test welcome email sending"""
        mock_send.return_value = Mock()

        send_welcome_email(self.user)

        mock_send.assert_called_once()
        args, kwargs = mock_send.call_args

        self.assertEqual(kwargs['template_key'], 'welcome')
        self.assertEqual(kwargs['to_email'], self.user.email)
        self.assertEqual(kwargs['user'], self.user)

        context = kwargs['context']
        self.assertEqual(context['user'], self.user)
        self.assertEqual(context['user_name'], self.user.get_full_name())
        self.assertEqual(context['login_url'], "/custom/login/")

    @patch.object(EmailService, 'send_email')
    def test_send_password_reset_email(self, mock_send):
        """Test password reset email sending"""
        mock_send.return_value = Mock()
        reset_link = "https://example.com/reset/token123"

        send_password_reset_email(self.user, reset_link)

        mock_send.assert_called_once()
        args, kwargs = mock_send.call_args

        self.assertEqual(kwargs['template_key'], 'password_reset')
        self.assertEqual(kwargs['to_email'], self.user.email)
        self.assertEqual(kwargs['user'], self.user)

        context = kwargs['context']
        self.assertEqual(context['user'], self.user)
        self.assertEqual(context['reset_link'], reset_link)

    @patch.object(EmailService, 'send_email')
    def test_send_notification_email(self, mock_send):
        """Test notification email sending"""
        mock_send.return_value = Mock()

        send_notification_email(
            user=self.user,
            title="Important Update",
            message="Your account has been updated",
            action_url="https://example.com/dashboard"
        )

        mock_send.assert_called_once()
        args, kwargs = mock_send.call_args

        self.assertEqual(kwargs['template_key'], 'notification')
        self.assertEqual(kwargs['to_email'], self.user.email)
        self.assertEqual(kwargs['user'], self.user)

        context = kwargs['context']
        self.assertEqual(context['title'], "Important Update")
        self.assertEqual(context['message'], "Your account has been updated")
        self.assertEqual(context['action_url'], "https://example.com/dashboard")


# Celery Task Tests
@pytest.mark.django_db
class TestEmailTasks:
    """Test Celery email tasks"""

    def test_send_email_task_success(self, user, email_template, celery_eager):
        """Test successful email task execution"""
        email_log = EmailMessageLog.objects.create(
            template=email_template,
            template_key=email_template.key,
            to_email="recipient@example.com",
            from_email="sender@example.com",
            subject="Test Email",
            html_content="<p>Test content</p>",
            text_content="Test content",
            user=user
        )

        with patch('apps.emails.services.EmailService._send_email_now') as mock_send:
            mock_send.return_value = True

            result = send_email_task(email_log.id)

            mock_send.assert_called_once_with(email_log)
            assert result['success'] is True
            assert result['email_log_id'] == email_log.id
            assert result['to_email'] == 'recipient@example.com'

    def test_send_email_task_failure(self, user, email_template, celery_eager):
        """Test failed email task execution"""
        email_log = EmailMessageLog.objects.create(
            template=email_template,
            template_key=email_template.key,
            to_email="recipient@example.com",
            from_email="sender@example.com",
            subject="Test Email",
            html_content="<p>Test content</p>",
            text_content="Test content",
            user=user
        )

        with patch('apps.emails.services.EmailService._send_email_now') as mock_send:
            mock_send.return_value = False
            email_log.error_message = "SMTP Error"

            result = send_email_task(email_log.id)

            assert result['success'] is False
            assert result['error'] == "SMTP Error"

    def test_send_email_task_email_not_found(self, celery_eager):
        """Test email task with non-existent email log"""
        result = send_email_task(99999)

        assert result['success'] is False
        assert 'not found' in result['error']

    def test_send_email_task_retry_on_exception(self, user, email_template):
        """Test email task retry mechanism"""
        email_log = EmailMessageLog.objects.create(
            template=email_template,
            template_key=email_template.key,
            to_email="recipient@example.com",
            from_email="sender@example.com",
            subject="Test Email",
            html_content="<p>Test content</p>",
            text_content="Test content",
            user=user
        )

        # Mock the task to track retry calls
        mock_task = Mock()
        mock_task.request = Mock()
        mock_task.request.retries = 0

        with patch('apps.emails.services.EmailService._send_email_now') as mock_send:
            mock_send.side_effect = Exception("Connection failed")
            mock_task.retry.side_effect = Retry("Retrying task")

            with patch('apps.emails.tasks.send_email_task', mock_task):
                with pytest.raises(Retry):
                    send_email_task.apply(args=[email_log.id]).get()

    def test_cleanup_old_email_logs(self, celery_eager):
        """Test cleanup of old email logs"""
        # Create old and recent email logs
        old_time = timezone.now() - timedelta(days=35)
        recent_time = timezone.now() - timedelta(days=5)

        with patch('django.utils.timezone.now', return_value=old_time):
            old_log = EmailMessageLog.objects.create(
                to_email="old@example.com",
                from_email="sender@example.com",
                subject="Old Email"
            )

        with patch('django.utils.timezone.now', return_value=recent_time):
            recent_log = EmailMessageLog.objects.create(
                to_email="recent@example.com",
                from_email="sender@example.com",
                subject="Recent Email"
            )

        # Override created_at since auto_now_add prevents manual setting
        EmailMessageLog.objects.filter(id=old_log.id).update(created_at=old_time)
        EmailMessageLog.objects.filter(id=recent_log.id).update(created_at=recent_time)

        result = cleanup_old_email_logs(days_to_keep=30)

        assert result['success'] is True
        assert result['deleted_count'] == 1

        # Check that only recent log remains
        assert not EmailMessageLog.objects.filter(id=old_log.id).exists()
        assert EmailMessageLog.objects.filter(id=recent_log.id).exists()

    def test_send_bulk_email_task(self, email_template, celery_eager):
        """Test bulk email sending task"""
        recipients = ["user1@example.com", "user2@example.com"]
        context = {"title": "Bulk Email", "user_name": "User"}

        with patch.object(EmailService, 'send_email') as mock_send:
            mock_send.return_value = Mock()

            result = send_bulk_email_task(
                template_key=email_template.key,
                recipient_emails=recipients,
                context=context
            )

            assert result['success'] is True
            assert result['sent_count'] == 2
            assert result['failed_count'] == 0
            assert mock_send.call_count == 2

    def test_send_bulk_email_task_with_failures(self, email_template, celery_eager):
        """Test bulk email task with some failures"""
        recipients = ["user1@example.com", "user2@example.com", "user3@example.com"]

        def mock_send_side_effect(*args, **kwargs):
            if kwargs['to_email'] == 'user2@example.com':
                raise Exception("Send failed")
            return Mock()

        with patch.object(EmailService, 'send_email') as mock_send:
            mock_send.side_effect = mock_send_side_effect

            result = send_bulk_email_task(
                template_key=email_template.key,
                recipient_emails=recipients,
                context={}
            )

            assert result['success'] is True
            assert result['sent_count'] == 2
            assert result['failed_count'] == 1
            assert len(result['failed_emails']) == 1
            assert result['failed_emails'][0]['email'] == 'user2@example.com'

    def test_retry_failed_emails(self, user, email_template, celery_eager):
        """Test retry of failed emails"""
        # Create failed email logs
        failed_log1 = EmailMessageLog.objects.create(
            template=email_template,
            to_email="failed1@example.com",
            from_email="sender@example.com",
            subject="Failed Email 1",
            status=EmailStatus.FAILED,
            user=user
        )

        failed_log2 = EmailMessageLog.objects.create(
            template=email_template,
            to_email="failed2@example.com",
            from_email="sender@example.com",
            subject="Failed Email 2",
            status=EmailStatus.FAILED,
            user=user
        )

        # Create successful email log (should be ignored)
        successful_log = EmailMessageLog.objects.create(
            template=email_template,
            to_email="success@example.com",
            from_email="sender@example.com",
            subject="Success Email",
            status=EmailStatus.SENT,
            user=user
        )

        with patch('apps.emails.tasks.send_email_task.delay') as mock_delay:
            mock_task = Mock()
            mock_task.id = "retry-task-123"
            mock_delay.return_value = mock_task

            result = retry_failed_emails()

            assert result['success'] is True
            assert result['retried_count'] == 2

            # Check that failed logs were reset and rescheduled
            failed_log1.refresh_from_db()
            failed_log2.refresh_from_db()

            assert failed_log1.status == EmailStatus.PENDING
            assert failed_log2.status == EmailStatus.PENDING
            assert failed_log1.celery_task_id == "retry-task-123"
            assert failed_log2.celery_task_id == "retry-task-123"

            # Check that successful log was not affected
            successful_log.refresh_from_db()
            assert successful_log.status == EmailStatus.SENT


@pytest.mark.django_db
class TestEmailViews:
    """Test email-related views"""

    @pytest.fixture(autouse=True)
    def setup(self):
        self.admin_user = User.objects.create_user(
            email="admin@example.com",
            password="adminpass123",
            is_staff=True,
            is_superuser=True
        )

        self.regular_user = User.objects.create_user(
            email="user@example.com",
            password="userpass123"
        )

        self.template = EmailTemplate.objects.create(
            key="test-template",
            name="Test Template",
            subject="Hello {{ user_name }}",
            html_content="<h1>Hello {{ user_name }}!</h1>",
            text_content="Hello {{ user_name }}!",
            is_active=True
        )

    def test_email_template_list_view_staff_required(self, client):
        """Test template list view requires staff access"""
        url = reverse('email_template_list')

        # Unauthenticated user should be redirected
        response = client.get(url)
        assert response.status_code == 302

        # Regular user should be redirected
        client.force_login(self.regular_user)
        response = client.get(url)
        assert response.status_code == 302

        # Staff user should have access
        client.force_login(self.admin_user)
        response = client.get(url)
        assert response.status_code == 200

    def test_email_template_list_view_content(self, client):
        """Test template list view shows templates"""
        client.force_login(self.admin_user)
        url = reverse('email_template_list')

        response = client.get(url)

        assert response.status_code == 200
        assert 'templates' in response.context
        templates = response.context['templates']
        assert self.template in templates

    def test_email_template_preview_view(self, client):
        """Test template preview view"""
        client.force_login(self.admin_user)
        url = reverse('email_template_preview', args=[self.template.key])

        response = client.get(url)

        assert response.status_code == 200
        assert response.context['email_template'] == self.template
        assert 'subject' in response.context
        assert 'html_content' in response.context
        assert 'render_success' in response.context

    @override_settings(DEBUG=True)
    def test_email_preview_html_view_debug(self, client):
        """Test HTML preview in DEBUG mode"""
        client.force_login(self.admin_user)
        url = reverse('email_preview_html', args=[self.template.key])

        response = client.get(url)

        assert response.status_code == 200
        content = response.content.decode()
        assert "<h1>Hello" in content

    @override_settings(DEBUG=False)
    def test_email_preview_html_view_production_staff_only(self, client):
        """Test HTML preview in production requires staff"""
        # Staff user should have access even in production
        client.force_login(self.admin_user)
        url = reverse('email_preview_html', args=[self.template.key])

        response = client.get(url)
        assert response.status_code == 200

        # Regular user should be denied in production
        client.force_login(self.regular_user)
        response = client.get(url)
        assert response.status_code == 403

    @override_settings(DEBUG=True)
    def test_email_preview_text_view(self, client):
        """Test text preview view"""
        client.force_login(self.admin_user)
        url = reverse('email_preview_text', args=[self.template.key])

        response = client.get(url)

        assert response.status_code == 200
        assert response['Content-Type'] == 'text/plain; charset=utf-8'
        content = response.content.decode()
        assert "Hello" in content

    @override_settings(DEBUG=True)
    def test_send_test_email_view(self, client):
        """Test sending test email"""
        client.force_login(self.admin_user)
        url = reverse('send_test_email', args=[self.template.key])

        with patch.object(EmailService, 'send_email') as mock_send:
            mock_email_log = Mock()
            mock_email_log.id = 123
            mock_send.return_value = mock_email_log

            data = {'to_email': 'test@example.com'}
            response = client.post(url, json.dumps(data), content_type='application/json')

            assert response.status_code == 200
            result = response.json()
            assert result['success'] is True
            assert result['email_log_id'] == 123

            mock_send.assert_called_once()

    @override_settings(DEBUG=True)
    def test_send_test_email_get_method_not_allowed(self, client):
        """Test that GET method is not allowed for test email"""
        client.force_login(self.admin_user)
        url = reverse('send_test_email', args=[self.template.key])

        response = client.get(url)
        assert response.status_code == 405

    @override_settings(DEBUG=False)
    def test_send_test_email_production_blocked(self, client):
        """Test test email is blocked in production"""
        client.force_login(self.admin_user)
        url = reverse('send_test_email', args=[self.template.key])

        response = client.post(url, '{}', content_type='application/json')
        assert response.status_code == 403

    def test_email_log_list_view(self, client, user, email_template):
        """Test email log list view"""
        client.force_login(self.admin_user)

        # Create some email logs
        EmailMessageLog.objects.create(
            template=email_template,
            to_email="test1@example.com",
            from_email="sender@example.com",
            subject="Test Email 1"
        )

        EmailMessageLog.objects.create(
            template=email_template,
            to_email="test2@example.com",
            from_email="sender@example.com",
            subject="Test Email 2"
        )

        url = reverse('email_log_list')
        response = client.get(url)

        assert response.status_code == 200
        assert 'email_logs' in response.context
        assert len(response.context['email_logs']) == 2

    def test_email_webhook_post_delivered(self, client, user, email_template):
        """Test webhook handling for delivered email"""
        email_log = EmailMessageLog.objects.create(
            template=email_template,
            to_email="test@example.com",
            from_email="sender@example.com",
            subject="Test Email",
            celery_task_id="webhook-test-123"
        )

        url = reverse('email_webhook')
        data = {
            'event': 'delivered',
            'message_id': 'webhook-test-123'
        }

        response = client.post(url, json.dumps(data), content_type='application/json')

        assert response.status_code == 200

        email_log.refresh_from_db()
        assert email_log.status == EmailStatus.DELIVERED
        assert email_log.delivered_at is not None

    def test_email_webhook_post_opened(self, client, user, email_template):
        """Test webhook handling for opened email"""
        email_log = EmailMessageLog.objects.create(
            template=email_template,
            to_email="test@example.com",
            from_email="sender@example.com",
            subject="Test Email",
            celery_task_id="webhook-test-456"
        )

        url = reverse('email_webhook')
        data = {
            'event': 'opened',
            'message_id': 'webhook-test-456'
        }

        response = client.post(url, json.dumps(data), content_type='application/json')

        assert response.status_code == 200

        email_log.refresh_from_db()
        assert email_log.status == EmailStatus.OPENED
        assert email_log.opened_at is not None

    def test_email_webhook_post_clicked(self, client, user, email_template):
        """Test webhook handling for clicked email"""
        email_log = EmailMessageLog.objects.create(
            template=email_template,
            to_email="test@example.com",
            from_email="sender@example.com",
            subject="Test Email",
            celery_task_id="webhook-test-789"
        )

        url = reverse('email_webhook')
        data = {
            'event': 'clicked',
            'message_id': 'webhook-test-789'
        }

        response = client.post(url, json.dumps(data), content_type='application/json')

        assert response.status_code == 200

        email_log.refresh_from_db()
        assert email_log.status == EmailStatus.CLICKED
        assert email_log.clicked_at is not None

    def test_email_webhook_post_bounced(self, client, user, email_template):
        """Test webhook handling for bounced email"""
        email_log = EmailMessageLog.objects.create(
            template=email_template,
            to_email="test@example.com",
            from_email="sender@example.com",
            subject="Test Email",
            celery_task_id="webhook-test-bounced"
        )

        url = reverse('email_webhook')
        data = {
            'event': 'bounced',
            'message_id': 'webhook-test-bounced'
        }

        response = client.post(url, json.dumps(data), content_type='application/json')

        assert response.status_code == 200

        email_log.refresh_from_db()
        assert email_log.status == 'bounced'

    def test_email_webhook_message_not_found(self, client):
        """Test webhook with non-existent message ID"""
        url = reverse('email_webhook')
        data = {
            'event': 'delivered',
            'message_id': 'non-existent-id'
        }

        response = client.post(url, json.dumps(data), content_type='application/json')

        # Should still return success even if message not found
        assert response.status_code == 200

    def test_email_webhook_get_method_not_allowed(self, client):
        """Test that GET method is not allowed for webhook"""
        url = reverse('email_webhook')
        response = client.get(url)
        assert response.status_code == 405

    def test_email_webhook_invalid_json(self, client):
        """Test webhook with invalid JSON"""
        url = reverse('email_webhook')

        response = client.post(url, 'invalid json', content_type='application/json')
        assert response.status_code == 400


@pytest.mark.django_db
class TestEmailURLs:
    """Test email URL routing"""

    def test_email_template_list_url(self):
        """Test email template list URL"""
        url = reverse('email_template_list')
        assert url == '/emails/'

    def test_email_template_preview_url(self):
        """Test email template preview URL"""
        url = reverse('email_template_preview', args=['welcome'])
        assert url == '/emails/welcome/'

    def test_email_preview_html_url(self):
        """Test email HTML preview URL"""
        url = reverse('email_preview_html', args=['welcome'])
        assert url == '/emails/welcome/html/'

    def test_email_preview_text_url(self):
        """Test email text preview URL"""
        url = reverse('email_preview_text', args=['welcome'])
        assert url == '/emails/welcome/text/'

    def test_send_test_email_url(self):
        """Test send test email URL"""
        url = reverse('send_test_email', args=['welcome'])
        assert url == '/emails/welcome/test/'

    def test_email_log_list_url(self):
        """Test email log list URL"""
        url = reverse('email_log_list')
        assert url == '/email-logs/'

    def test_email_webhook_url(self):
        """Test email webhook URL"""
        url = reverse('email_webhook')
        assert url == '/webhooks/email/'


# Integration Tests
@pytest.mark.django_db
class TestEmailIntegration:
    """Integration tests for email functionality"""

    @pytest.fixture(autouse=True)
    def setup(self):
        self.user = User.objects.create_user(
            email="integration@example.com",
            password="testpass123",
            name="Integration User"
        )

        self.welcome_template = EmailTemplate.objects.create(
            key="welcome",
            name="Welcome Email",
            subject="Welcome {{ user_name }}!",
            html_content="""
            <h1>Welcome {{ user_name }}!</h1>
            <p>Thanks for joining our platform.</p>
            <a href="{{ login_url }}">Login here</a>
            """,
            text_content="""
            Welcome {{ user_name }}!
            Thanks for joining our platform.
            Login: {{ login_url }}
            """,
            is_active=True,
            category="auth"
        )

    @override_settings(
        EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend',
        DEFAULT_FROM_EMAIL='test@example.com'
    )
    def test_complete_email_flow_sync(self):
        """Test complete email flow synchronously"""
        # Clear email outbox
        mail.outbox = []

        # Send welcome email
        email_log = send_welcome_email(
            user=self.user,
            context={'extra_info': 'Welcome bonus!'}
        )

        # Check email log was created
        assert email_log.template_key == 'welcome'
        assert email_log.to_email == self.user.email
        assert email_log.user == self.user
        assert 'Integration User' in email_log.subject
        assert 'Welcome bonus!' in email_log.html_content

        # Since we're using async_send=True by default, task should be scheduled
        assert email_log.celery_task_id != ''

    @override_settings(
        EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend',
        CELERY_TASK_ALWAYS_EAGER=True,
        DEFAULT_FROM_EMAIL='test@example.com'
    )
    def test_complete_email_flow_with_celery(self, celery_eager):
        """Test complete email flow with Celery task execution"""
        # Clear email outbox
        mail.outbox = []

        # Send welcome email (will execute task immediately due to EAGER setting)
        email_log = send_welcome_email(self.user)

        # Check email was actually sent
        assert len(mail.outbox) == 1
        sent_email = mail.outbox[0]

        assert sent_email.to == [self.user.email]
        assert 'Integration User' in sent_email.subject
        assert len(sent_email.alternatives) == 1  # HTML alternative

        # Check email log was updated
        email_log.refresh_from_db()
        assert email_log.status == EmailStatus.SENT
        assert email_log.sent_at is not None

    def test_email_template_caching(self, clear_cache):
        """Test email template caching behavior"""
        # First access should hit database
        with patch.object(EmailTemplate.objects, 'get') as mock_get:
            mock_get.return_value = self.welcome_template

            template1 = EmailTemplate.get_template('welcome')
            assert template1 == self.welcome_template
            mock_get.assert_called_once()

        # Second access should use cache
        with patch.object(EmailTemplate.objects, 'get') as mock_get:
            template2 = EmailTemplate.get_template('welcome')
            assert template2 == self.welcome_template
            mock_get.assert_not_called()

        # Saving template should clear cache
        self.welcome_template.description = "Updated description"
        self.welcome_template.save()

        # Next access should hit database again
        with patch.object(EmailTemplate.objects, 'get') as mock_get:
            mock_get.return_value = self.welcome_template

            EmailTemplate.get_template('welcome')
            mock_get.assert_called_once()

    def test_bulk_email_sending(self):
        """Test bulk email functionality"""
        recipients = [
            'user1@example.com',
            'user2@example.com',
            'user3@example.com'
        ]

        with patch.object(EmailService, 'send_email') as mock_send:
            mock_send.return_value = Mock()

            email_logs = EmailService.send_bulk_email(
                template_key='welcome',
                recipients=recipients,
                context={'campaign': 'bulk_welcome'}
            )

            assert len(email_logs) == 3
            assert mock_send.call_count == 3

            # Check each call had correct recipient
            calls = mock_send.call_args_list
            sent_recipients = [call[1]['to_email'] for call in calls]
            assert set(sent_recipients) == set(recipients)

    def test_failed_email_retry_mechanism(self, celery_eager):
        """Test retry mechanism for failed emails"""
        # Create a failed email log
        failed_log = EmailMessageLog.objects.create(
            template=self.welcome_template,
            template_key='welcome',
            to_email='failed@example.com',
            from_email='test@example.com',
            subject='Welcome!',
            status=EmailStatus.FAILED,
            error_message='Original error',
            user=self.user
        )

        # Mock successful retry
        with patch('apps.emails.tasks.send_email_task.delay') as mock_delay:
            mock_task = Mock()
            mock_task.id = 'retry-task-123'
            mock_delay.return_value = mock_task

            result = retry_failed_emails()

            assert result['success'] is True
            assert result['retried_count'] == 1

            # Check email log was reset
            failed_log.refresh_from_db()
            assert failed_log.status == EmailStatus.PENDING
            assert failed_log.error_message == ''
            assert failed_log.celery_task_id == 'retry-task-123'

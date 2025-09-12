import logging
from typing import Any, Dict, List, Optional, Union

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.mail import EmailMultiAlternatives

from .models import EmailMessageLog, EmailTemplate
from .tasks import send_email_task

logger = logging.getLogger(__name__)
User = get_user_model()


class EmailService:
    """Service for sending emails using templates"""

    @staticmethod
    def send_email(
        template_key: str,
        to_email: Union[str, List[str]],
        context: Optional[Dict[str, Any]] = None,
        from_email: Optional[str] = None,
        cc: Optional[List[str]] = None,
        bcc: Optional[List[str]] = None,
        language: str = "en",
        user: Optional[User] = None,
        async_send: bool = True,
        **kwargs,
    ) -> EmailMessageLog:
        """
        Send email using template

        Args:
            template_key: Email template key
            to_email: Recipient email address(es)
            context: Template context data
            from_email: Sender email (defaults to settings.DEFAULT_FROM_EMAIL)
            cc: CC recipients
            bcc: BCC recipients
            language: Template language
            user: User who triggered the email
            async_send: Whether to send asynchronously via Celery
            **kwargs: Additional email parameters

        Returns:
            EmailMessageLog: Created email log entry
        """
        # Normalize to_email to string for database storage
        if isinstance(to_email, list):
            primary_recipient = to_email[0]
            # For multiple recipients, we'll create separate log entries
        else:
            primary_recipient = to_email

        # Get template
        template = EmailTemplate.get_template(template_key, language)
        if not template:
            raise ValueError(
                f"Email template '{template_key}' not found for language '{language}'"
            )

        # Prepare context
        email_context = context or {}

        # Render email content
        try:
            rendered_content = template.render_all(email_context)
        except Exception as e:
            logger.error(f"Failed to render email template {template_key}: {str(e)}")
            raise ValueError(f"Failed to render email template: {str(e)}")

        # Create email log
        email_log = EmailMessageLog.objects.create(
            template=template,
            template_key=template_key,
            to_email=primary_recipient,
            from_email=from_email or settings.DEFAULT_FROM_EMAIL,
            cc=cc or [],
            bcc=bcc or [],
            subject=rendered_content["subject"],
            html_content=rendered_content["html_content"],
            text_content=rendered_content["text_content"],
            context_data=email_context,
            user=user,
        )

        # Send email
        if async_send:
            # Send asynchronously via Celery
            task = send_email_task.delay(email_log.id)
            email_log.celery_task_id = task.id
            email_log.save(update_fields=["celery_task_id"])
        else:
            # Send synchronously
            EmailService._send_email_now(email_log)

        return email_log

    @staticmethod
    def _send_email_now(email_log: EmailMessageLog) -> bool:
        """Send email immediately (synchronous)"""
        try:
            # Prepare recipients
            to_emails = [email_log.to_email]
            cc_emails = email_log.cc_list
            bcc_emails = email_log.bcc_list

            # Create email message
            msg = EmailMultiAlternatives(
                subject=email_log.subject,
                body=email_log.text_content,
                from_email=email_log.from_email,
                to=to_emails,
                cc=cc_emails,
                bcc=bcc_emails,
            )

            # Add HTML alternative if available
            if email_log.html_content:
                msg.attach_alternative(email_log.html_content, "text/html")

            # Send email
            msg.send(fail_silently=False)

            # Mark as sent
            email_log.mark_as_sent()

            logger.info(f"Email sent successfully to {email_log.to_email}")
            return True

        except Exception as e:
            error_message = str(e)
            logger.error(
                f"Failed to send email to {email_log.to_email}: {error_message}"
            )

            # Mark as failed
            email_log.mark_as_failed(error_message)
            return False

    @staticmethod
    def send_template_email(
        template_key: str,
        to_email: str,
        context: Optional[Dict[str, Any]] = None,
        **kwargs,
    ) -> EmailMessageLog:
        """Convenience method for sending template emails"""
        return EmailService.send_email(
            template_key=template_key,
            to_email=to_email,
            context=context,
            **kwargs,
        )

    @staticmethod
    def send_bulk_email(
        template_key: str,
        recipients: List[str],
        context: Optional[Dict[str, Any]] = None,
        **kwargs,
    ) -> List[EmailMessageLog]:
        """Send email to multiple recipients"""
        email_logs = []

        for recipient in recipients:
            try:
                email_log = EmailService.send_email(
                    template_key=template_key,
                    to_email=recipient,
                    context=context,
                    **kwargs,
                )
                email_logs.append(email_log)
            except Exception as e:
                logger.error(f"Failed to send email to {recipient}: {str(e)}")

        return email_logs

    @staticmethod
    def preview_email(
        template_key: str,
        context: Optional[Dict[str, Any]] = None,
        language: str = "en",
    ) -> Dict[str, str]:
        """Preview email content without sending"""
        template = EmailTemplate.get_template(template_key, language)
        if not template:
            raise ValueError(f"Email template '{template_key}' not found")

        return template.render_all(context or {})


# Convenience functions for common email types
def send_welcome_email(
    user: User, context: Optional[Dict[str, Any]] = None
) -> EmailMessageLog:
    """Send welcome email to new user"""
    email_context = {
        "user": user,
        "user_name": user.get_full_name(),
        "login_url": (
            settings.LOGIN_URL if hasattr(settings, "LOGIN_URL") else "/auth/login/"
        ),
        **(context or {}),
    }

    return EmailService.send_email(
        template_key="welcome",
        to_email=user.email,
        context=email_context,
        user=user,
    )


def send_password_reset_email(
    user: User, reset_link: str, context: Optional[Dict[str, Any]] = None
) -> EmailMessageLog:
    """Send password reset email"""
    email_context = {
        "user": user,
        "user_name": user.get_full_name(),
        "reset_link": reset_link,
        **(context or {}),
    }

    return EmailService.send_email(
        template_key="password_reset",
        to_email=user.email,
        context=email_context,
        user=user,
    )


def send_notification_email(
    user: User,
    title: str,
    message: str,
    action_url: Optional[str] = None,
    context: Optional[Dict[str, Any]] = None,
) -> EmailMessageLog:
    """Send notification email"""
    email_context = {
        "user": user,
        "user_name": user.get_full_name(),
        "title": title,
        "message": message,
        "action_url": action_url,
        **(context or {}),
    }

    return EmailService.send_email(
        template_key="notification",
        to_email=user.email,
        context=email_context,
        user=user,
    )

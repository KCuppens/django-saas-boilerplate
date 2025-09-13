"""Email services for the Django SaaS boilerplate."""

import json
import logging
from typing import Any, Optional, Union

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.mail import EmailMultiAlternatives
from django.db import models

from apps.core.enums import EmailStatus

from .models import EmailMessageLog, EmailTemplate
from .tasks import send_email_task

logger = logging.getLogger(__name__)
User = get_user_model()


class EmailService:
    """Service for sending emails using templates."""

    @staticmethod
    def send_email(
        template_key: str,
        to_email: Union[str, list[str]],
        context: Optional[dict[str, Any]] = None,
        from_email: Optional[str] = None,
        cc: Optional[list[str]] = None,
        bcc: Optional[list[str]] = None,
        language: str = "en",
        user: Optional[User] = None,
        async_send: bool = True,
        **kwargs,
    ) -> EmailMessageLog:
        """
        Send email using template.

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
        # Normalize recipients and format for storage
        normalized_recipients = EmailService._normalize_recipients(to_email)
        recipient_string = EmailService._format_recipients_for_storage(
            normalized_recipients
        )

        # Get template (first check if it exists, then if it's active)
        try:
            template = EmailTemplate.objects.get(key=template_key, language=language)
        except EmailTemplate.DoesNotExist:
            # Try to get default language template
            if language != "en":
                try:
                    template = EmailTemplate.objects.get(
                        key=template_key, language="en"
                    )
                except EmailTemplate.DoesNotExist:
                    raise EmailTemplate.DoesNotExist(
                        f"Email template '{template_key}' not found for "
                        f"language '{language}'"
                    )
            else:
                raise EmailTemplate.DoesNotExist(
                    f"Email template '{template_key}' not found for "
                    f"language '{language}'"
                )

        # Check if template is active
        if not template.is_active:
            raise ValueError(f"Email template '{template_key}' is not active")

        # Prepare context
        email_context = EmailService._get_template_context(template, context, user)

        # Validate context
        EmailService._validate_template_context(email_context)

        # Render email content
        try:
            rendered_content = template.render_all(email_context)
        except Exception as e:
            logger.error("Failed to render email template %s: %s", template_key, str(e))
            raise ValueError(f"Failed to render email template: {str(e)}")

        # Create email log
        email_log = EmailService._create_email_log(
            template=template,
            to_email=recipient_string,
            from_email=from_email or settings.DEFAULT_FROM_EMAIL,
            cc=cc,
            bcc=bcc,
            subject=rendered_content["subject"],
            html_body=rendered_content["html_content"],
            text_body=rendered_content["text_content"],
            user=user,
        )
        # Store context_data without Django model instances (for JSON serialization)
        storable_context = {}
        for key, value in email_context.items():
            if not isinstance(value, models.Model):
                storable_context[key] = value

        email_log.context_data = storable_context
        email_log.save(update_fields=["context_data"])

        # Send email
        if async_send:
            # Send asynchronously via Celery
            task = send_email_task.delay(email_log.id)
            email_log.celery_task_id = task.id
            email_log.save(update_fields=["celery_task_id"])
        else:
            # Send synchronously
            EmailService._send_email_now(email_log)
            # Refresh from database to get updated status
            email_log.refresh_from_db()

        return email_log

    @staticmethod
    def _send_email_now(email_log: EmailMessageLog) -> bool:
        """Send email immediately (synchronous)."""
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

            logger.info("Email sent successfully to %s", email_log.to_email)
            return True

        except Exception as e:
            error_message = str(e)
            logger.error(
                "Failed to send email to %s: %s", email_log.to_email, error_message
            )

            # Mark as failed
            email_log.mark_as_failed(error_message)
            return False

    @staticmethod
    def send_template_email(
        template_key: str,
        to_email: str,
        context: Optional[dict[str, Any]] = None,
        **kwargs,
    ) -> EmailMessageLog:
        """Send template emails using a convenience method."""
        return EmailService.send_email(
            template_key=template_key,
            to_email=to_email,
            context=context,
            **kwargs,
        )

    @staticmethod
    def send_bulk_email(
        template_key: str,
        recipients: list[str],
        context: Optional[dict[str, Any]] = None,
        **kwargs,
    ) -> dict[str, Any]:
        """Send email to multiple recipients."""
        email_logs = []
        failed_emails = []
        total_sent = 0
        total_failed = 0

        for recipient in recipients:
            try:
                email_log = EmailService.send_email(
                    template_key=template_key,
                    to_email=recipient,
                    context=context,
                    async_send=False,  # Send synchronously for bulk operations
                    **kwargs,
                )
                email_logs.append(email_log)

                # Check the status after sending
                email_log.refresh_from_db()
                if email_log.status == EmailStatus.SENT:
                    total_sent += 1
                else:
                    total_failed += 1
                    failed_emails.append(recipient)

            except Exception as e:
                logger.error("Failed to send email to %s: %s", recipient, str(e))
                total_failed += 1
                failed_emails.append(recipient)

        return {
            "total_sent": total_sent,
            "total_failed": total_failed,
            "failed_emails": failed_emails,
        }

    @staticmethod
    def preview_email(
        template_key: str,
        context: Optional[dict[str, Any]] = None,
        language: str = "en",
    ) -> dict[str, str]:
        """Preview email content without sending."""
        template = EmailTemplate.get_template(template_key, language)
        if not template:
            raise ValueError(f"Email template '{template_key}' not found")

        return template.render_all(context or {})

    @staticmethod
    def _get_template_context(
        template: EmailTemplate,
        context: Optional[dict[str, Any]] = None,
        user: Optional[User] = None,
    ) -> dict[str, Any]:
        """Get template context with default values."""
        email_context = {
            "site_name": getattr(settings, "SITE_NAME", "Your Site"),
            "site_url": getattr(settings, "SITE_URL", "http://localhost:8000"),
        }

        # Add user context if provided
        if user:
            email_context["user"] = user

        # Add custom context
        if context:
            email_context.update(context)

        return email_context

    @staticmethod
    def _validate_template_context(context: dict[str, Any]) -> None:
        """Validate template context data."""
        if not isinstance(context, dict):
            raise ValueError("Template context must be a dictionary")

        # Check for non-serializable values (excluding Django models and
        # special objects)
        try:
            # Create a copy without Django model instances for testing
            test_context = {}
            for key, value in context.items():
                if isinstance(value, models.Model):
                    # Skip Django model instances - they're fine in templates
                    continue
                elif hasattr(value, "__dict__") and not hasattr(value, "__json__"):
                    # This is likely an object() or similar
                    raise ValueError(f"Non-serializable object: {type(value)}")
                else:
                    test_context[key] = value

            # Test serialization of remaining values
            json.dumps(test_context)

        except (TypeError, ValueError) as e:
            raise ValueError(
                f"Template context contains non-serializable values: {str(e)}"
            )

    @staticmethod
    def _normalize_recipients(to_email: Union[str, list[str]]) -> list[str]:
        """Normalize recipients to a list."""
        if isinstance(to_email, str):
            return [to_email]
        elif isinstance(to_email, list):
            return to_email
        else:
            raise ValueError("Recipients must be a string or list of strings")

    @staticmethod
    def _format_recipients_for_storage(recipients: list[str]) -> str:
        """Format recipients list for database storage."""
        return ", ".join(recipients)

    @staticmethod
    def _create_email_log(
        template: EmailTemplate,
        to_email: str,
        from_email: str,
        cc: Optional[list[str]] = None,
        bcc: Optional[list[str]] = None,
        subject: str = "",
        html_body: str = "",
        text_body: str = "",
        user: Optional[User] = None,
    ) -> EmailMessageLog:
        """Create email log entry."""
        email_log = EmailMessageLog.objects.create(
            template=template,
            template_key=template.key,
            to_email=to_email,
            from_email=from_email,
            subject=subject,
            html_content=html_body,
            text_content=text_body,
            user=user,
            status=EmailStatus.PENDING,
        )

        # Set CC and BCC using the property setters
        email_log.cc_list = cc or []
        email_log.bcc_list = bcc or []
        email_log.save(update_fields=["cc", "bcc"])

        return email_log


# Convenience functions for common email types
def send_welcome_email(
    user: User, context: Optional[dict[str, Any]] = None
) -> EmailMessageLog:
    """Send welcome email to new user."""
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
    user: User, reset_link: str, context: Optional[dict[str, Any]] = None
) -> EmailMessageLog:
    """Send password reset email."""
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
    context: Optional[dict[str, Any]] = None,
) -> EmailMessageLog:
    """Send notification email."""
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

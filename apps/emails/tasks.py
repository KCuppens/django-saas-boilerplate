import logging

from celery import shared_task

from .models import EmailMessageLog

logger = logging.getLogger(__name__)


@shared_task(name="apps.emails.tasks.send_email_task", bind=True)
def send_email_task(self, email_log_id: int):
    """
    Celery task to send email asynchronously

    Args:
        email_log_id: ID of EmailMessageLog to send

    Returns:
        dict: Task result with success status and details
    """
    try:
        from .services import EmailService

        # Get email log
        email_log = EmailMessageLog.objects.get(id=email_log_id)

        # Send email
        success = EmailService._send_email_now(email_log)

        if success:
            logger.info(f"Email task completed successfully for {email_log.to_email}")
            return {
                "success": True,
                "email_log_id": email_log_id,
                "to_email": email_log.to_email,
                "subject": email_log.subject,
            }
        else:
            logger.error(f"Email task failed for {email_log.to_email}")
            return {
                "success": False,
                "email_log_id": email_log_id,
                "to_email": email_log.to_email,
                "error": email_log.error_message,
            }

    except EmailMessageLog.DoesNotExist:
        error_msg = f"EmailMessageLog with id {email_log_id} not found"
        logger.error(error_msg)
        return {
            "success": False,
            "error": error_msg,
            "email_log_id": email_log_id,
        }

    except Exception as e:
        error_msg = f"Unexpected error in email task: {str(e)}"
        logger.error(error_msg)

        # Try to mark email as failed if we have the log
        try:
            email_log = EmailMessageLog.objects.get(id=email_log_id)
            email_log.mark_as_failed(error_msg)
        except EmailMessageLog.DoesNotExist:
            pass

        # Retry the task up to 3 times with exponential backoff
        raise self.retry(exc=e, countdown=60 * (2**self.request.retries), max_retries=3)


@shared_task(name="apps.emails.tasks.cleanup_old_email_logs")
def cleanup_old_email_logs(days_to_keep: int = 30):
    """
    Celery task to clean up old email logs

    Args:
        days_to_keep: Number of days to keep email logs (default: 30)

    Returns:
        dict: Task result with cleanup details
    """
    try:
        from datetime import timedelta

        from django.utils import timezone

        cutoff_date = timezone.now() - timedelta(days=days_to_keep)

        # Delete old email logs
        deleted_count, _ = EmailMessageLog.objects.filter(
            created_at__lt=cutoff_date
        ).delete()

        logger.info(f"Cleaned up {deleted_count} old email logs")

        return {
            "success": True,
            "deleted_count": deleted_count,
            "cutoff_date": cutoff_date.isoformat(),
            "days_kept": days_to_keep,
        }

    except Exception as e:
        error_msg = f"Failed to cleanup old email logs: {str(e)}"
        logger.error(error_msg)
        return {"success": False, "error": error_msg}


@shared_task(name="apps.emails.tasks.send_bulk_email_task")
def send_bulk_email_task(
    template_key: str, recipient_emails: list, context: dict | None = None
):
    """
    Celery task to send bulk emails

    Args:
        template_key: Email template key
        recipient_emails: List of recipient email addresses
        context: Template context data

    Returns:
        dict: Task result with bulk send details
    """
    try:
        from .services import EmailService

        sent_count = 0
        failed_count = 0
        failed_emails = []

        for email in recipient_emails:
            try:
                EmailService.send_email(
                    template_key=template_key,
                    to_email=email,
                    context=context or {},
                    async_send=False,  # Send synchronously within this task
                )
                sent_count += 1
            except Exception as e:
                failed_count += 1
                failed_emails.append({"email": email, "error": str(e)})
                logger.error(f"Failed to send bulk email to {email}: {str(e)}")

        logger.info(
            f"Bulk email task completed: {sent_count} sent, {failed_count} failed"
        )

        return {
            "success": True,
            "sent_count": sent_count,
            "failed_count": failed_count,
            "failed_emails": failed_emails,
            "template_key": template_key,
            "total_recipients": len(recipient_emails),
        }

    except Exception as e:
        error_msg = f"Bulk email task failed: {str(e)}"
        logger.error(error_msg)
        return {
            "success": False,
            "error": error_msg,
            "template_key": template_key,
            "total_recipients": (len(recipient_emails) if recipient_emails else 0),
        }


@shared_task(name="apps.emails.tasks.retry_failed_emails")
def retry_failed_emails(max_retries: int = 3):
    """
    Celery task to retry failed emails

    Args:
        max_retries: Maximum number of retry attempts

    Returns:
        dict: Task result with retry details
    """
    try:
        from datetime import timedelta

        from django.utils import timezone

        from apps.core.enums import EmailStatus

        # Get failed emails from the last 24 hours
        cutoff_time = timezone.now() - timedelta(hours=24)
        failed_emails = EmailMessageLog.objects.filter(
            status=EmailStatus.FAILED, created_at__gte=cutoff_time
        )[
            :100
        ]  # Limit to 100 at a time

        retried_count = 0
        success_count = 0

        for email_log in failed_emails:
            try:
                # Reset status to pending
                email_log.status = EmailStatus.PENDING
                email_log.error_message = ""
                email_log.save(update_fields=["status", "error_message"])

                # Retry sending
                task = send_email_task.delay(email_log.id)  # type: ignore
                email_log.celery_task_id = task.id
                email_log.save(update_fields=["celery_task_id"])

                retried_count += 1

            except Exception as e:
                logger.error(
                    f"Failed to retry email {email_log.id}: {str(e)}"
                )

        logger.info(f"Retried {retried_count} failed emails")

        return {
            "success": True,
            "retried_count": retried_count,
            "success_count": success_count,
        }

    except Exception as e:
        error_msg = f"Failed to retry failed emails: {str(e)}"
        logger.error(error_msg)
        return {"success": False, "error": error_msg}

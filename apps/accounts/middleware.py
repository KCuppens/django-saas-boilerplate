"""Middleware for user account functionality."""

from django.utils import timezone
from django.utils.deprecation import MiddlewareMixin


class LastSeenMiddleware(MiddlewareMixin):
    """Middleware to update user's last_seen timestamp on each request."""

    def process_request(self, request):
        """Update last_seen for authenticated users."""
        if request.user.is_authenticated:
            try:
                # Update last_seen every 5 minutes to avoid too many DB writes
                now = timezone.now()
                if not hasattr(request.user, "last_seen") or (
                    request.user.last_seen
                    and (now - request.user.last_seen).seconds > 300
                ):
                    request.user.update_last_seen()
            except Exception as e:
                # Handle cases where user or profile might not exist or have issues
                # Log the error for debugging purposes
                import logging
                logger = logging.getLogger(__name__)
                logger.debug(f"Failed to update user last_seen: {e}")
        return None

"""Custom authentication classes for the Django SaaS boilerplate."""

from rest_framework import exceptions
from rest_framework.authentication import SessionAuthentication


class CustomSessionAuthentication(SessionAuthentication):
    """Custom Session Authentication that returns 401 instead of 403.

    This authentication class returns 401 instead of 403
    when no authentication credentials are provided.
    """

    def authenticate(self, request):
        """Return a User and Token if session authentication is valid.

        Return a `User` and `Token` if a valid session-based
        authentication has taken place. Otherwise return `None`.
        """
        # Get the session-based user on the request
        user = getattr(request._request, "user", None)

        # If user is not authenticated, return None (which will cause 401)
        if not user or not user.is_authenticated:
            return None

        # Check session
        if not hasattr(user, "is_active") or not user.is_active:
            raise exceptions.AuthenticationFailed("User inactive or deleted.")

        return (user, None)

    def authenticate_header(self, request):
        """Return WWW-Authenticate header value for 401 responses.

        Return a string to be used as the value of the `WWW-Authenticate`
        header in a `401 Unauthorized` response.
        """
        return "Session"

from rest_framework import authentication, exceptions
from rest_framework.authentication import SessionAuthentication


class CustomSessionAuthentication(SessionAuthentication):
    """
    Custom Session Authentication that returns 401 instead of 403
    when no authentication credentials are provided.
    """

    def authenticate(self, request):
        """
        Returns a `User` and `Token` if a valid session-based
        authentication has taken place. Otherwise returns `None`.
        """
        # Get the session-based user on the request
        user = getattr(request._request, 'user', None)

        # If user is not authenticated, return None (which will cause 401)
        if not user or not user.is_authenticated:
            return None

        # Check session
        if not hasattr(user, 'is_active') or not user.is_active:
            raise exceptions.AuthenticationFailed('User inactive or deleted.')

        return (user, None)

    def authenticate_header(self, request):
        """
        Return a string to be used as the value of the `WWW-Authenticate`
        header in a `401 Unauthorized` response.
        """
        return 'Session'
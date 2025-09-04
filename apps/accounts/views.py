from allauth.account import app_settings as allauth_settings
from django.contrib.auth import get_user_model
from drf_spectacular.utils import extend_schema, extend_schema_view
from rest_framework import permissions, status
from rest_framework.decorators import action
from rest_framework.mixins import RetrieveModelMixin, UpdateModelMixin
from rest_framework.response import Response
from rest_framework.throttling import AnonRateThrottle, UserRateThrottle
from rest_framework.viewsets import GenericViewSet

from .serializers import (
    PasswordChangeSerializer,
    UserRegistrationSerializer,
    UserSerializer,
    UserUpdateSerializer,
)

User = get_user_model()


class AuthThrottle(AnonRateThrottle):
    """Custom throttle for authentication endpoints"""

    scope = "auth"
    rate = "5/min"


@extend_schema_view(
    retrieve=extend_schema(
        summary="Get current user profile",
        description="Retrieve the current authenticated user's profile information.",
    ),
    update=extend_schema(
        summary="Update user profile",
        description="Update the current authenticated user's profile information.",
    ),
    partial_update=extend_schema(
        summary="Partially update user profile",
        description="Partially update the current authenticated user's profile information.",
    ),
)
class UserViewSet(RetrieveModelMixin, UpdateModelMixin, GenericViewSet):
    """ViewSet for user profile management"""

    serializer_class = UserSerializer
    permission_classes = [permissions.IsAuthenticated]
    throttle_classes = [UserRateThrottle]

    def get_object(self):
        """Return the current user"""
        return self.request.user

    def get_serializer_class(self):
        """Return appropriate serializer class"""
        if self.action in ["update", "partial_update"]:
            return UserUpdateSerializer
        return UserSerializer

    @extend_schema(
        summary="Register new user",
        description="Register a new user account. Email verification will be required if enabled.",
        request=UserRegistrationSerializer,
        responses={201: UserSerializer},
    )
    @action(
        detail=False,
        methods=["post"],
        permission_classes=[permissions.AllowAny],
        throttle_classes=[AuthThrottle],
        url_path="register",
    )
    def register(self, request):
        """Register a new user"""
        serializer = UserRegistrationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        user = serializer.save(request)

        # Return user data
        user_serializer = UserSerializer(user, context={"request": request})

        return Response(
            {
                "user": user_serializer.data,
                "message": "Registration successful. Please check your email to verify your account."
                if allauth_settings.EMAIL_VERIFICATION
                == allauth_settings.EmailVerificationMethod.MANDATORY
                else "Registration successful.",
            },
            status=status.HTTP_201_CREATED,
        )

    @extend_schema(
        summary="Change password",
        description="Change the current user's password.",
        request=PasswordChangeSerializer,
        responses={
            200: {"type": "object", "properties": {"message": {"type": "string"}}}
        },
    )
    @action(detail=False, methods=["post"], url_path="change-password")
    def change_password(self, request):
        """Change user password"""
        serializer = PasswordChangeSerializer(
            data=request.data, context={"request": request}
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()

        return Response({"message": "Password changed successfully."})

    @extend_schema(
        summary="Update last seen timestamp",
        description="Update the user's last seen timestamp.",
        responses={
            200: {"type": "object", "properties": {"message": {"type": "string"}}}
        },
    )
    @action(detail=False, methods=["post"], url_path="ping")
    def ping(self, request):
        """Update user's last seen timestamp"""
        request.user.update_last_seen()
        return Response(
            {"message": "Last seen updated.", "last_seen": request.user.last_seen}
        )

    @extend_schema(
        summary="Delete user account",
        description="Delete the current user's account permanently.",
        responses={204: None},
    )
    @action(detail=False, methods=["delete"], url_path="delete-account")
    def delete_account(self, request):
        """Delete user account"""
        user = request.user
        user.is_active = False
        user.save()

        # You might want to actually delete the user or just deactivate
        # For compliance reasons, you might want to keep the user record
        # user.delete()

        return Response(status=status.HTTP_204_NO_CONTENT)

from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    EmailVerificationView,
    PasswordResetConfirmView,
    PasswordResetView,
    ProfileUpdateView,
    UserViewSet,
)

router = DefaultRouter()
router.register(r"users", UserViewSet, basename="user")

urlpatterns = [
    path("", include(router.urls)),
    # Additional URL patterns for the missing functionality
    path(
        "profile/update/",
        ProfileUpdateView.as_view({"post": "post"}),
        name="api-profile-update",
    ),
    path(
        "password-reset/",
        PasswordResetView.as_view({"post": "post"}),
        name="api-password-reset",
    ),
    path(
        "password-reset/confirm/",
        PasswordResetConfirmView.as_view({"post": "post"}),
        name="api-password-reset-confirm",
    ),
    path(
        "verify-email/",
        EmailVerificationView.as_view({"post": "post"}),
        name="api-verify-email",
    ),
]

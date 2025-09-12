"""Global pytest configuration and fixtures"""

import os
import sys
from pathlib import Path

import django
import pytest

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

# Setup Django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "apps.config.settings.test")
django.setup()

from django.contrib.auth import get_user_model  # noqa: E402
from django.contrib.auth.models import Group  # noqa: E402
from rest_framework.test import APIClient  # noqa: E402

User = get_user_model()


@pytest.fixture
def user():
    """Create a test user"""
    return User.objects.create_user(
        email="test@example.com",
        password="testpass123",  # nosec B106
        name="Test User",
    )


@pytest.fixture
def admin_user():
    """Create an admin user"""
    user = User.objects.create_user(
        email="admin@example.com",
        password="adminpass123",  # nosec B106
        name="Admin User",
        is_staff=True,
        is_superuser=True,
    )

    # Add to Admin group if it exists
    admin_group, _ = Group.objects.get_or_create(name="Admin")
    user.groups.add(admin_group)

    return user


@pytest.fixture
def manager_user():
    """Create a manager user"""
    user = User.objects.create_user(
        email="manager@example.com",
        password="managerpass123",  # nosec B106
        name="Manager User",
    )

    # Add to Manager group if it exists
    manager_group, _ = Group.objects.get_or_create(name="Manager")
    user.groups.add(manager_group)

    return user


@pytest.fixture
def member_user():
    """Create a member user"""
    user = User.objects.create_user(
        email="member@example.com",
        password="memberpass123",  # nosec B106
        name="Member User",
    )

    # Add to Member group if it exists
    member_group, _ = Group.objects.get_or_create(name="Member")
    user.groups.add(member_group)

    return user


@pytest.fixture
def api_client():
    """Create an API client"""
    return APIClient()


@pytest.fixture
def auth_client(user):
    """Create an authenticated API client"""
    client = APIClient()
    client.force_authenticate(user=user)
    return client


@pytest.fixture
def admin_client(admin_user):
    """Create an admin API client"""
    client = APIClient()
    client.force_authenticate(user=admin_user)
    return client


@pytest.fixture(autouse=True)
def celery_eager(settings):
    """Configure Celery to execute tasks synchronously for tests"""
    settings.CELERY_TASK_ALWAYS_EAGER = True
    settings.CELERY_TASK_EAGER_PROPAGATES = True


@pytest.fixture
def mailpit(settings):
    """Configure mailpit for email testing"""
    settings.EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"


@pytest.fixture
def groups():
    """Create default user groups"""
    admin_group, _ = Group.objects.get_or_create(name="Admin")
    manager_group, _ = Group.objects.get_or_create(name="Manager")
    member_group, _ = Group.objects.get_or_create(name="Member")
    readonly_group, _ = Group.objects.get_or_create(name="ReadOnly")

    return {
        "admin": admin_group,
        "manager": manager_group,
        "member": member_group,
        "readonly": readonly_group,
    }


@pytest.fixture
def sample_file():
    """Create a sample file for testing"""
    from django.core.files.uploadedfile import SimpleUploadedFile

    return SimpleUploadedFile(
        "test.txt", b"This is a test file content", content_type="text/plain"
    )


@pytest.fixture
def sample_image():
    """Create a sample image for testing"""
    import io

    from django.core.files.uploadedfile import SimpleUploadedFile
    from PIL import Image

    # Create a simple image
    image = Image.new("RGB", (100, 100), color="red")
    image_io = io.BytesIO()
    image.save(image_io, format="PNG")
    image_io.seek(0)

    return SimpleUploadedFile("test.png", image_io.getvalue(), content_type="image/png")

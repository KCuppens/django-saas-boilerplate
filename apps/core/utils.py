import hashlib
import secrets
import uuid
from typing import Any

from django.conf import settings
from django.core.mail import send_mail
from django.utils import timezone
from django.utils.text import slugify


def generate_uuid():
    """Generate a UUID4 string"""
    return str(uuid.uuid4())


def generate_short_uuid(length=8):
    """Generate a short UUID-like string"""
    return str(uuid.uuid4()).replace("-", "")[:length]


def generate_secure_token(length=32):
    """Generate a cryptographically secure random token"""
    return secrets.token_urlsafe(length)


def generate_hash(data: str, algorithm="sha256"):
    """Generate hash of data using specified algorithm"""
    hash_func = getattr(hashlib, algorithm)
    return hash_func(data.encode()).hexdigest()


def create_slug(text: str, max_length: int = 50) -> str:
    """Create a URL-friendly slug from text"""
    slug = slugify(text)
    if len(slug) > max_length:
        slug = slug[:max_length].rstrip("-")
    return slug


def safe_get_dict_value(
    dictionary: dict[str, Any], key: str, default: Any = None
) -> Any:
    """Safely get value from dictionary with default"""
    try:
        return dictionary.get(key, default)
    except (KeyError, AttributeError):
        return default


def truncate_string(text: str, max_length: int = 100, suffix: str = "...") -> str:
    """Truncate string to specified length with suffix"""
    if len(text) <= max_length:
        return text
    return text[: max_length - len(suffix)] + suffix


def format_file_size(size_bytes: int) -> str:
    """Format file size in bytes to human readable format"""
    if size_bytes == 0:
        return "0 B"

    size_names = ["B", "KB", "MB", "GB", "TB"]
    i = 0
    size_float = float(size_bytes)
    while size_float >= 1024 and i < len(size_names) - 1:
        size_float /= 1024.0
        i += 1

    return f"{size_float:.1f} {size_names[i]}"


def get_client_ip(request) -> str:
    """Get client IP address from request"""
    x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
    if x_forwarded_for:
        ip = x_forwarded_for.split(",")[0]
    else:
        ip = request.META.get("REMOTE_ADDR")
    return ip


def get_user_agent(request) -> str:
    """Get user agent from request"""
    return request.META.get("HTTP_USER_AGENT", "")


def time_since_creation(created_at) -> str:
    """Get human-readable time since creation"""
    now = timezone.now()
    diff = now - created_at

    if diff.days > 0:
        return f"{diff.days} days ago"
    elif diff.seconds > 3600:
        hours = diff.seconds // 3600
        return f"{hours} hours ago"
    elif diff.seconds > 60:
        minutes = diff.seconds // 60
        return f"{minutes} minutes ago"
    else:
        return "Just now"


def send_notification_email(
    subject: str,
    message: str,
    recipient_list: list,
    from_email: str | None = None,
    fail_silently: bool = False,
) -> bool:
    """Send notification email"""
    try:
        send_mail(
            subject=subject,
            message=message,
            from_email=from_email or settings.DEFAULT_FROM_EMAIL,
            recipient_list=recipient_list,
            fail_silently=fail_silently,
        )
        return True
    except Exception as e:
        if not fail_silently:
            raise e
        return False


def mask_email(email: str) -> str:
    """Mask email address for privacy"""
    if "@" not in email:
        return email

    local, domain = email.split("@", 1)
    if len(local) <= 2:
        masked_local = local[0] + "*" * (len(local) - 1)
    else:
        masked_local = local[0] + "*" * (len(local) - 2) + local[-1]

    return f"{masked_local}@{domain}"


def validate_json_structure(
    data: dict[str, Any], required_fields: list
) -> dict[str, Any]:
    """Validate JSON data has required fields"""
    errors = {}
    for field in required_fields:
        if field not in data:
            errors[field] = f"Field '{field}' is required"

    return errors

import re

from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _


def validate_phone_number(value):
    """Validate phone number format"""
    phone_regex = re.compile(r'^\+?1?\d{9,15}$')
    if not phone_regex.match(value):
        raise ValidationError(
            _('Invalid phone number format. Use international format: +1234567890')
        )


def validate_no_special_chars(value):
    """Validate that value contains no special characters"""
    if not re.match(r'^[a-zA-Z0-9\s]*$', value):
        raise ValidationError(
            _('This field can only contain letters, numbers, and spaces.')
        )


def validate_alphanumeric(value):
    """Validate that value contains only alphanumeric characters"""
    if not re.match(r'^[a-zA-Z0-9]*$', value):
        raise ValidationError(
            _('This field can only contain letters and numbers.')
        )


def validate_slug_format(value):
    """Validate slug format (lowercase letters, numbers, hyphens)"""
    if not re.match(r'^[a-z0-9-]*$', value):
        raise ValidationError(
            _('This field can only contain lowercase letters, numbers, and hyphens.')
        )


def validate_file_size(value, max_size_mb=5):
    """Validate file size (in MB)"""
    max_size_bytes = max_size_mb * 1024 * 1024
    if value.size > max_size_bytes:
        raise ValidationError(
            _('File size cannot exceed {max_size} MB.').format(max_size=max_size_mb)
        )


def validate_image_dimensions(value, max_width=1920, max_height=1080):
    """Validate image dimensions"""
    from PIL import Image

    try:
        with Image.open(value) as img:
            width, height = img.size
            if width > max_width or height > max_height:
                raise ValidationError(
                    _('Image dimensions cannot exceed {max_width}x{max_height} pixels.')
                    .format(max_width=max_width, max_height=max_height)
                )
    except Exception:
        raise ValidationError(_('Invalid image file.'))


class FileValidator:
    """Flexible file validator class"""

    def __init__(self, max_size_mb=None, allowed_extensions=None, allowed_content_types=None):
        self.max_size_mb = max_size_mb
        self.allowed_extensions = allowed_extensions or []
        self.allowed_content_types = allowed_content_types or []

    def __call__(self, value):
        # Check file size
        if self.max_size_mb:
            validate_file_size(value, self.max_size_mb)

        # Check file extension
        if self.allowed_extensions:
            import os
            ext = os.path.splitext(value.name)[1].lower()
            if ext not in [f'.{ext}' for ext in self.allowed_extensions]:
                raise ValidationError(
                    _('File extension not allowed. Allowed extensions: {extensions}')
                    .format(extensions=', '.join(self.allowed_extensions))
                )

        # Check content type
        if self.allowed_content_types:
            if value.content_type not in self.allowed_content_types:
                raise ValidationError(
                    _('File type not allowed. Allowed types: {types}')
                    .format(types=', '.join(self.allowed_content_types))
                )

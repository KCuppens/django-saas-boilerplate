from django.contrib.auth.models import AbstractUser, Group
from django.db import models
from django.utils import timezone
from django.core.validators import FileExtensionValidator


class User(AbstractUser):
    """Custom user model with email as username"""
    
    username = None  # Remove username field
    email = models.EmailField("Email address", unique=True)
    name = models.CharField("Full name", max_length=150, blank=True)
    avatar = models.ImageField(
        "Avatar",
        upload_to="avatars/%Y/%m/%d/",
        blank=True,
        null=True,
        validators=[FileExtensionValidator(allowed_extensions=['jpg', 'jpeg', 'png', 'gif'])]
    )
    last_seen = models.DateTimeField("Last seen", default=timezone.now)
    
    # Additional fields for SaaS features
    created_at = models.DateTimeField("Created", auto_now_add=True)
    updated_at = models.DateTimeField("Updated", auto_now=True)
    
    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = []
    
    class Meta:
        verbose_name = "User"
        verbose_name_plural = "Users"
        ordering = ["-created_at"]
    
    def __str__(self):
        return self.email
    
    def get_full_name(self):
        """Return the full name for the user."""
        return self.name or self.email
    
    def get_short_name(self):
        """Return the short name for the user."""
        return self.name.split(' ')[0] if self.name else self.email.split('@')[0]
    
    def update_last_seen(self):
        """Update the last_seen timestamp"""
        self.last_seen = timezone.now()
        self.save(update_fields=['last_seen'])
    
    def has_group(self, group_name):
        """Check if user belongs to a specific group"""
        return self.groups.filter(name=group_name).exists()
    
    def is_admin(self):
        """Check if user is an admin"""
        return self.has_group('Admin') or self.is_superuser
    
    def is_manager(self):
        """Check if user is a manager or admin"""
        return self.has_group('Manager') or self.is_admin()
    
    def is_member(self):
        """Check if user is a member, manager, or admin"""
        return self.has_group('Member') or self.is_manager()


class UserProfile(models.Model):
    """Extended user profile information"""
    
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    
    # Profile fields
    bio = models.TextField("Biography", max_length=500, blank=True)
    location = models.CharField("Location", max_length=100, blank=True)
    website = models.URLField("Website", blank=True)
    phone = models.CharField("Phone number", max_length=20, blank=True)
    
    # Preferences
    timezone = models.CharField("Timezone", max_length=50, default="UTC")
    language = models.CharField("Language", max_length=10, default="en")
    receive_notifications = models.BooleanField("Receive notifications", default=True)
    receive_marketing_emails = models.BooleanField("Receive marketing emails", default=False)
    
    # Timestamps
    created_at = models.DateTimeField("Created", auto_now_add=True)
    updated_at = models.DateTimeField("Updated", auto_now=True)
    
    class Meta:
        verbose_name = "User Profile"
        verbose_name_plural = "User Profiles"
    
    def __str__(self):
        return f"{self.user.email} Profile"
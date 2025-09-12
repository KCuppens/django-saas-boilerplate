from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password

from allauth.account.adapter import get_adapter
from allauth.account.utils import setup_user_email
from rest_framework import serializers

from .models import UserProfile

User = get_user_model()


class UserProfileSerializer(serializers.ModelSerializer):
    """Serializer for UserProfile"""

    class Meta:
        model = UserProfile
        fields = [
            "bio",
            "location",
            "website",
            "phone",
            "timezone",
            "language",
            "receive_notifications",
            "receive_marketing_emails",
        ]


class UserSerializer(serializers.ModelSerializer):
    """Serializer for User model"""

    profile = UserProfileSerializer(read_only=True)
    full_name = serializers.CharField(source="get_full_name", read_only=True)
    short_name = serializers.CharField(source="get_short_name", read_only=True)
    avatar_url = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            "id",
            "email",
            "name",
            "avatar",
            "avatar_url",
            "full_name",
            "short_name",
            "last_seen",
            "is_active",
            "date_joined",
            "created_at",
            "updated_at",
            "profile",
        ]
        read_only_fields = [
            "id",
            "last_seen",
            "date_joined",
            "created_at",
            "updated_at",
        ]

    def get_avatar_url(self, obj):
        """Get avatar URL"""
        if obj.avatar:
            request = self.context.get("request")
            if request:
                return request.build_absolute_uri(obj.avatar.url)
            return obj.avatar.url
        return None


class UserRegistrationSerializer(serializers.Serializer):
    """Serializer for user registration"""

    email = serializers.EmailField()
    name = serializers.CharField(max_length=150, required=False, allow_blank=True)
    password1 = serializers.CharField(write_only=True)
    password2 = serializers.CharField(write_only=True)

    def validate_email(self, email):
        """Validate email is not already registered"""
        email = get_adapter().clean_email(email)
        if User.objects.filter(email__iexact=email).exists():
            raise serializers.ValidationError(
                "A user is already registered with this email address."
            )
        return email

    def validate(self, data):
        """Validate passwords match and meet requirements"""
        if data["password1"] != data["password2"]:
            raise serializers.ValidationError("The two password fields didn't match.")

        password = data.get("password1")
        try:
            validate_password(password)
        except Exception as e:
            raise serializers.ValidationError({"password1": list(e.messages)})

        return data

    def save(self, request):
        """Create and return a new user"""
        adapter = get_adapter()
        user = adapter.new_user(request)
        user.email = self.validated_data.get("email")
        user.name = self.validated_data.get("name", "")

        adapter.save_user(request, user, form=None)
        setup_user_email(request, user, [])
        user.set_password(self.validated_data.get("password1"))
        user.save()

        return user


class PasswordChangeSerializer(serializers.Serializer):
    """Serializer for password change"""

    old_password = serializers.CharField(write_only=True)
    new_password1 = serializers.CharField(write_only=True)
    new_password2 = serializers.CharField(write_only=True)

    def validate_old_password(self, value):
        """Validate old password is correct"""
        user = self.context["request"].user
        if not user.check_password(value):
            raise serializers.ValidationError(
                "Your old password was entered incorrectly."
            )
        return value

    def validate(self, data):
        """Validate new passwords match and meet requirements"""
        if data["new_password1"] != data["new_password2"]:
            raise serializers.ValidationError("The two password fields didn't match.")

        password = data.get("new_password1")
        user = self.context["request"].user
        try:
            validate_password(password, user)
        except Exception as e:
            raise serializers.ValidationError({"new_password1": list(e.messages)})

        return data

    def save(self):
        """Change user password"""
        user = self.context["request"].user
        password = self.validated_data["new_password1"]
        user.set_password(password)
        user.save()
        return user


class UserUpdateSerializer(serializers.ModelSerializer):
    """Serializer for updating user profile"""

    profile = UserProfileSerializer(required=False)

    class Meta:
        model = User
        fields = ["name", "avatar", "profile"]

    def update(self, instance, validated_data):
        """Update user and profile"""
        profile_data = validated_data.pop("profile", None)

        # Update user fields
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()

        # Update profile fields
        if profile_data and hasattr(instance, "profile"):
            profile = instance.profile
            for attr, value in profile_data.items():
                setattr(profile, attr, value)
            profile.save()

        return instance

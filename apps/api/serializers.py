from rest_framework import serializers

from .models import APIKey, Note


class NoteSerializer(serializers.ModelSerializer):
    """Serializer for Note model"""

    created_by_name = serializers.CharField(
        source="created_by.get_full_name", read_only=True
    )
    updated_by_name = serializers.CharField(
        source="updated_by.get_full_name", read_only=True
    )
    tag_list = serializers.ListField(
        child=serializers.CharField(max_length=50),
        required=False,
        help_text="List of tags",
    )

    class Meta:
        model = Note
        fields = [
            "id",
            "title",
            "content",
            "is_public",
            "tags",
            "tag_list",
            "created_at",
            "updated_at",
            "created_by",
            "created_by_name",
            "updated_by",
            "updated_by_name",
        ]
        read_only_fields = [
            "id",
            "created_at",
            "updated_at",
            "created_by",
            "created_by_name",
            "updated_by",
            "updated_by_name",
        ]

    def to_internal_value(self, data):
        """Convert tag_list to tags field"""
        if "tag_list" in data and isinstance(data["tag_list"], list):
            data = data.copy()
            data["tags"] = ", ".join(data["tag_list"])
        return super().to_internal_value(data)

    def to_representation(self, instance):
        """Convert tags field to tag_list"""
        data = super().to_representation(instance)
        if instance.tags:
            data["tag_list"] = instance.tag_list
        else:
            data["tag_list"] = []
        return data


class NoteCreateUpdateSerializer(NoteSerializer):
    """Serializer for creating/updating notes"""

    class Meta(NoteSerializer.Meta):
        fields = [
            "id",
            "title",
            "content",
            "is_public",
            "tag_list",
            "created_at",
            "updated_at",
            "created_by_name",
        ]
        read_only_fields = ["id", "created_at", "updated_at", "created_by_name"]


class HealthCheckSerializer(serializers.Serializer):
    """Serializer for health check response"""

    status = serializers.CharField()
    timestamp = serializers.DateTimeField()
    version = serializers.CharField(required=False)
    database = serializers.BooleanField()
    cache = serializers.BooleanField()
    celery = serializers.BooleanField(required=False)

    # Additional health metrics
    uptime = serializers.CharField(required=False)
    memory_usage = serializers.FloatField(required=False)
    cpu_usage = serializers.FloatField(required=False)

    # Service-specific checks
    services = serializers.DictField(required=False)
    errors = serializers.ListField(required=False)


class APIKeySerializer(serializers.ModelSerializer):
    """Serializer for APIKey model"""
    
    permissions = serializers.ListField(
        child=serializers.ChoiceField(choices=['read', 'write', 'admin']),
        required=False,
        default=list,
        help_text="List of permissions for this API key"
    )

    class Meta:
        model = APIKey
        fields = [
            "id",
            "name",
            "key",
            "permissions",
            "is_active",
            "user",
            "last_used",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "key",
            "user",
            "last_used",
            "created_at",
            "updated_at",
        ]


class APIKeyCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating API keys"""
    
    permissions = serializers.ListField(
        child=serializers.ChoiceField(choices=['read', 'write', 'admin']),
        required=False,
        default=list,
        help_text="List of permissions for this API key"
    )

    class Meta:
        model = APIKey
        fields = ["id", "name", "key", "permissions", "is_active", "created_at"]
        read_only_fields = ["id", "key", "created_at"]

    def create(self, validated_data):
        """Create API key with current user"""
        validated_data["user"] = self.context["request"].user
        return super().create(validated_data)

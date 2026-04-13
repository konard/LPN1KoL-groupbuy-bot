"""
Serializers for User API
"""
from rest_framework import serializers
from .models import User, UserSession


class UserSerializer(serializers.ModelSerializer):
    """User serializer for read operations.

    ``selfie_file_id`` is intentionally excluded — it is only accessible via
    the Django admin interface.
    """
    role_display = serializers.ReadOnlyField()
    full_name = serializers.ReadOnlyField()

    class Meta:
        model = User
        fields = [
            'id', 'platform', 'platform_user_id', 'username',
            'first_name', 'last_name', 'full_name', 'phone', 'email',
            'role', 'role_display', 'balance', 'language_code',
            'is_active', 'is_verified', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'balance', 'is_verified', 'created_at', 'updated_at']


class UserRegistrationSerializer(serializers.ModelSerializer):
    """Serializer for user registration.

    Only ``phone`` is required.  Name fields are taken from the messenger
    profile and may be empty (users control what personal data they share).
    Email is intentionally not collected at registration time.

    ``selfie_file_id`` is accepted on write (stored for admin review) but is
    not returned in the response to keep the file_id private.
    """

    first_name = serializers.CharField(required=False, allow_blank=True, default='')
    last_name = serializers.CharField(required=False, allow_blank=True, default='')
    phone = serializers.CharField(required=False, allow_blank=True, default='')
    email = serializers.EmailField(required=False, allow_blank=True, default='')
    selfie_file_id = serializers.CharField(required=False, allow_blank=True, default='', write_only=True)

    class Meta:
        model = User
        fields = [
            'id', 'platform', 'platform_user_id', 'username',
            'first_name', 'last_name', 'phone', 'email',
            'role', 'language_code', 'selfie_file_id'
        ]
        read_only_fields = ['id']

    def validate_phone(self, value):
        if value and not value.startswith('+'):
            value = '+' + value
        return value


class UserProfileUpdateSerializer(serializers.ModelSerializer):
    """Serializer for profile updates"""

    class Meta:
        model = User
        fields = ['first_name', 'last_name', 'phone', 'email', 'role']


class UserBalanceSerializer(serializers.Serializer):
    """Serializer for balance information"""
    balance = serializers.DecimalField(max_digits=12, decimal_places=2)
    total_deposited = serializers.DecimalField(max_digits=12, decimal_places=2, default=0)
    total_spent = serializers.DecimalField(max_digits=12, decimal_places=2, default=0)
    available = serializers.DecimalField(max_digits=12, decimal_places=2)


class UserSessionSerializer(serializers.ModelSerializer):
    """Serializer for user sessions"""

    class Meta:
        model = UserSession
        fields = ['id', 'dialog_type', 'dialog_state', 'dialog_data', 'expires_at', 'created_at']


class CheckAccessSerializer(serializers.Serializer):
    """Serializer for access check requests"""
    user_id = serializers.IntegerField()

"""
Admin API Serializers
"""
from rest_framework import serializers
from users.models import User
from procurements.models import Category, Procurement, Participant
from payments.models import Payment, Transaction
from chat.models import Message, Notification


class DashboardStatsSerializer(serializers.Serializer):
    """Serializer for dashboard statistics."""
    total_users = serializers.IntegerField()
    users_by_role = serializers.DictField()
    users_by_platform = serializers.DictField()
    new_users_today = serializers.IntegerField()
    new_users_week = serializers.IntegerField()
    new_users_month = serializers.IntegerField()

    total_procurements = serializers.IntegerField()
    procurements_by_status = serializers.DictField()
    active_procurements = serializers.IntegerField()
    completed_procurements = serializers.IntegerField()

    total_payments = serializers.IntegerField()
    payments_by_status = serializers.DictField()
    total_revenue = serializers.DecimalField(max_digits=15, decimal_places=2)
    revenue_today = serializers.DecimalField(max_digits=15, decimal_places=2)
    revenue_week = serializers.DecimalField(max_digits=15, decimal_places=2)
    revenue_month = serializers.DecimalField(max_digits=15, decimal_places=2)

    total_messages = serializers.IntegerField()
    messages_today = serializers.IntegerField()


class AdminUserSerializer(serializers.ModelSerializer):
    """Serializer for User model in admin context."""
    full_name = serializers.CharField(read_only=True)
    role_display = serializers.CharField(read_only=True)
    participations_count = serializers.SerializerMethodField()
    organized_count = serializers.SerializerMethodField()
    total_spent = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            'id', 'platform', 'platform_user_id', 'username',
            'first_name', 'last_name', 'full_name', 'phone', 'email',
            'role', 'role_display', 'balance', 'language_code',
            'is_active', 'is_verified', 'created_at', 'updated_at',
            'participations_count', 'organized_count', 'total_spent'
        ]
        read_only_fields = ['created_at', 'updated_at']

    def get_participations_count(self, obj):
        return obj.participations.count()

    def get_organized_count(self, obj):
        return obj.organized_procurements.count()

    def get_total_spent(self, obj):
        from django.db.models import Sum
        total = obj.transactions.filter(amount__lt=0).aggregate(
            total=Sum('amount')
        )['total'] or 0
        return abs(total)


class AdminUserUpdateSerializer(serializers.ModelSerializer):
    """Serializer for updating User in admin context."""

    class Meta:
        model = User
        fields = [
            'first_name', 'last_name', 'phone', 'email',
            'role', 'balance', 'is_active', 'is_verified'
        ]


class AdminProcurementSerializer(serializers.ModelSerializer):
    """Serializer for Procurement model in admin context."""
    organizer_name = serializers.CharField(source='organizer.full_name', read_only=True)
    category_name = serializers.CharField(source='category.name', read_only=True, allow_null=True)
    participant_count = serializers.IntegerField(read_only=True)
    progress = serializers.IntegerField(read_only=True)
    status_display = serializers.CharField(read_only=True)

    class Meta:
        model = Procurement
        fields = [
            'id', 'title', 'description', 'category', 'category_name',
            'organizer', 'organizer_name', 'supplier', 'city', 'delivery_address',
            'target_amount', 'current_amount', 'stop_at_amount', 'unit', 'price_per_unit',
            'status', 'status_display', 'deadline', 'payment_deadline',
            'image_url', 'is_featured', 'created_at', 'updated_at',
            'participant_count', 'progress'
        ]
        read_only_fields = ['current_amount', 'created_at', 'updated_at']


class AdminProcurementUpdateSerializer(serializers.ModelSerializer):
    """Serializer for updating Procurement in admin context."""

    class Meta:
        model = Procurement
        fields = [
            'title', 'description', 'category', 'status',
            'is_featured', 'deadline', 'payment_deadline'
        ]


class AdminParticipantSerializer(serializers.ModelSerializer):
    """Serializer for Participant model in admin context."""
    user_name = serializers.CharField(source='user.full_name', read_only=True)
    procurement_title = serializers.CharField(source='procurement.title', read_only=True)

    class Meta:
        model = Participant
        fields = [
            'id', 'user', 'user_name', 'procurement', 'procurement_title',
            'quantity', 'amount', 'status', 'notes', 'is_active',
            'created_at', 'updated_at'
        ]


class AdminPaymentSerializer(serializers.ModelSerializer):
    """Serializer for Payment model in admin context."""
    user_name = serializers.CharField(source='user.full_name', read_only=True)
    status_display = serializers.CharField(read_only=True)

    class Meta:
        model = Payment
        fields = [
            'id', 'user', 'user_name', 'payment_type', 'amount', 'status',
            'status_display', 'external_id', 'provider', 'confirmation_url',
            'procurement', 'description', 'metadata',
            'paid_at', 'created_at', 'updated_at'
        ]


class AdminTransactionSerializer(serializers.ModelSerializer):
    """Serializer for Transaction model in admin context."""
    user_name = serializers.CharField(source='user.full_name', read_only=True)

    class Meta:
        model = Transaction
        fields = [
            'id', 'user', 'user_name', 'transaction_type', 'amount',
            'balance_after', 'payment', 'procurement', 'description', 'created_at'
        ]


class AdminCategorySerializer(serializers.ModelSerializer):
    """Serializer for Category model in admin context."""
    procurements_count = serializers.SerializerMethodField()

    class Meta:
        model = Category
        fields = [
            'id', 'name', 'description', 'parent', 'icon',
            'is_active', 'created_at', 'procurements_count'
        ]

    def get_procurements_count(self, obj):
        return obj.procurements.count()


class AdminMessageSerializer(serializers.ModelSerializer):
    """Serializer for Message model in admin context."""
    user_name = serializers.CharField(source='user.full_name', read_only=True)
    procurement_title = serializers.CharField(source='procurement.title', read_only=True)

    class Meta:
        model = Message
        fields = [
            'id', 'user', 'user_name', 'procurement', 'procurement_title',
            'message_type', 'text', 'is_deleted', 'created_at', 'updated_at'
        ]


class AdminNotificationSerializer(serializers.ModelSerializer):
    """Serializer for Notification model in admin context."""
    user_name = serializers.CharField(source='user.full_name', read_only=True)

    class Meta:
        model = Notification
        fields = [
            'id', 'user', 'user_name', 'notification_type', 'title',
            'message', 'is_read', 'procurement', 'created_at'
        ]


class AdminLoginSerializer(serializers.Serializer):
    """Serializer for admin login."""
    username = serializers.CharField()
    password = serializers.CharField(write_only=True)


class AdminUserInfoSerializer(serializers.Serializer):
    """Serializer for admin user info."""
    id = serializers.IntegerField()
    username = serializers.CharField()
    email = serializers.EmailField()
    is_staff = serializers.BooleanField()
    is_superuser = serializers.BooleanField()


class BulkActionSerializer(serializers.Serializer):
    """Serializer for bulk actions."""
    ids = serializers.ListField(child=serializers.IntegerField())
    action = serializers.CharField()

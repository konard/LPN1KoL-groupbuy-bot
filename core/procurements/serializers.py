"""
Serializers for Procurements API
"""
from rest_framework import serializers
from .models import Category, Procurement, Participant, SupplierVote


class CategorySerializer(serializers.ModelSerializer):
    """Category serializer"""

    class Meta:
        model = Category
        fields = ['id', 'name', 'description', 'parent', 'icon', 'is_active']


class ParticipantSerializer(serializers.ModelSerializer):
    """Participant serializer"""
    user_name = serializers.CharField(source='user.full_name', read_only=True)

    class Meta:
        model = Participant
        fields = [
            'id', 'user', 'user_name', 'quantity', 'amount',
            'status', 'notes', 'is_active', 'created_at'
        ]
        read_only_fields = ['id', 'created_at']


class SupplierVoteSerializer(serializers.ModelSerializer):
    """Serializer for supplier votes"""
    voter_name = serializers.CharField(source='voter.full_name', read_only=True)
    supplier_name = serializers.CharField(source='supplier.full_name', read_only=True)

    class Meta:
        model = SupplierVote
        fields = ['id', 'procurement', 'voter', 'voter_name', 'supplier', 'supplier_name', 'comment', 'created_at']
        read_only_fields = ['id', 'created_at']


class CastVoteSerializer(serializers.Serializer):
    """Serializer for casting a supplier vote"""
    voter_id = serializers.IntegerField()
    supplier_id = serializers.IntegerField()
    comment = serializers.CharField(required=False, allow_blank=True)


class ProcurementListSerializer(serializers.ModelSerializer):
    """Procurement serializer for list view"""
    category_name = serializers.CharField(source='category.name', read_only=True)
    organizer_name = serializers.CharField(source='organizer.full_name', read_only=True)
    progress = serializers.ReadOnlyField()
    participant_count = serializers.ReadOnlyField()
    days_left = serializers.ReadOnlyField()
    can_join = serializers.ReadOnlyField()

    class Meta:
        model = Procurement
        fields = [
            'id', 'title', 'category', 'category_name', 'organizer', 'organizer_name',
            'city', 'target_amount', 'current_amount', 'progress',
            'participant_count', 'status', 'deadline', 'days_left',
            'can_join', 'image_url', 'is_featured', 'commission_percent'
        ]


class ProcurementDetailSerializer(serializers.ModelSerializer):
    """Procurement serializer for detail view"""
    category_name = serializers.CharField(source='category.name', read_only=True)
    organizer_name = serializers.CharField(source='organizer.full_name', read_only=True)
    progress = serializers.ReadOnlyField()
    participant_count = serializers.ReadOnlyField()
    days_left = serializers.ReadOnlyField()
    status_display = serializers.ReadOnlyField()
    can_join = serializers.ReadOnlyField()
    participants = ParticipantSerializer(many=True, read_only=True)

    class Meta:
        model = Procurement
        fields = [
            'id', 'title', 'description', 'category', 'category_name',
            'organizer', 'organizer_name', 'supplier',
            'city', 'delivery_address',
            'target_amount', 'current_amount', 'stop_at_amount',
            'unit', 'price_per_unit', 'commission_percent', 'min_quantity', 'progress',
            'status', 'status_display', 'deadline', 'payment_deadline',
            'days_left', 'can_join', 'participant_count',
            'image_url', 'is_featured', 'participants',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'current_amount', 'created_at', 'updated_at']


class ProcurementCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating procurements"""

    class Meta:
        model = Procurement
        fields = [
            'id', 'title', 'description', 'category', 'organizer',
            'city', 'delivery_address',
            'target_amount', 'stop_at_amount', 'unit', 'price_per_unit',
            'commission_percent', 'min_quantity',
            'deadline', 'payment_deadline', 'image_url'
        ]
        read_only_fields = ['id']


class JoinProcurementSerializer(serializers.Serializer):
    """Serializer for joining a procurement"""
    user_id = serializers.IntegerField()
    quantity = serializers.DecimalField(max_digits=10, decimal_places=2, default=1)
    amount = serializers.DecimalField(max_digits=12, decimal_places=2)
    notes = serializers.CharField(required=False, allow_blank=True)


class AddParticipantSerializer(serializers.Serializer):
    """Serializer for adding another user to a procurement (organizer action)"""
    user_id = serializers.IntegerField()
    organizer_id = serializers.IntegerField()
    quantity = serializers.DecimalField(max_digits=10, decimal_places=2, default=1)
    amount = serializers.DecimalField(max_digits=12, decimal_places=2)
    notes = serializers.CharField(required=False, allow_blank=True)


class InviteUserSerializer(serializers.Serializer):
    """Serializer for inviting a user to a procurement by email (creator only)"""
    email = serializers.EmailField()
    organizer_id = serializers.IntegerField(required=False)

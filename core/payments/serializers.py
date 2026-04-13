"""
Serializers for Payments API
"""
from rest_framework import serializers
from .models import Payment, Transaction


class PaymentSerializer(serializers.ModelSerializer):
    """Payment serializer"""
    status_display = serializers.ReadOnlyField()
    provider_display = serializers.CharField(source='get_provider_display', read_only=True)

    class Meta:
        model = Payment
        fields = [
            'id', 'user', 'payment_type', 'amount', 'status', 'status_display',
            'external_id', 'order_id', 'provider', 'provider_display', 'confirmation_url',
            'procurement', 'description', 'paid_at', 'created_at'
        ]
        read_only_fields = ['id', 'external_id', 'order_id', 'paid_at', 'created_at']


class CreatePaymentSerializer(serializers.Serializer):
    """Serializer for creating a payment"""
    user_id = serializers.IntegerField()
    amount = serializers.DecimalField(max_digits=12, decimal_places=2)
    description = serializers.CharField(required=False, allow_blank=True)
    procurement_id = serializers.IntegerField(required=False)


class TransactionSerializer(serializers.ModelSerializer):
    """Transaction serializer"""
    procurement_title = serializers.CharField(source='procurement.title', read_only=True)

    class Meta:
        model = Transaction
        fields = [
            'id', 'user', 'transaction_type', 'amount', 'balance_after',
            'payment', 'procurement', 'procurement_title',
            'description', 'created_at'
        ]
        read_only_fields = ['id', 'balance_after', 'created_at']


class WebhookPayloadSerializer(serializers.Serializer):
    """Serializer for webhook payload (YooKassa/Tochka)"""
    type = serializers.CharField(required=False)
    event = serializers.CharField(required=False)
    eventType = serializers.CharField(required=False)  # Tochka format
    object = serializers.DictField(required=False)
    payment = serializers.DictField(required=False)  # Tochka format

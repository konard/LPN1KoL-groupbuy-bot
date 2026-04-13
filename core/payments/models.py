"""
Payment models for GroupBuy Bot
Supports Tochka Bank Cyclops and YooKassa (legacy) integration
"""
from django.db import models
from users.models import User
from procurements.models import Procurement


class Payment(models.Model):
    """Payment record for deposits and withdrawals"""

    class Status(models.TextChoices):
        PENDING = 'pending', 'Pending'
        WAITING_FOR_CAPTURE = 'waiting_for_capture', 'Waiting for Capture'
        SUCCEEDED = 'succeeded', 'Succeeded'
        CANCELLED = 'cancelled', 'Cancelled'
        REFUNDED = 'refunded', 'Refunded'

    class PaymentType(models.TextChoices):
        DEPOSIT = 'deposit', 'Deposit'
        WITHDRAWAL = 'withdrawal', 'Withdrawal'
        PROCUREMENT_PAYMENT = 'procurement_payment', 'Procurement Payment'

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='payments')
    payment_type = models.CharField(max_length=30, choices=PaymentType.choices)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    status = models.CharField(max_length=30, choices=Status.choices, default=Status.PENDING)

    class Provider(models.TextChoices):
        TOCHKA = 'tochka', 'Tochka Bank (Cyclops)'
        YOOKASSA = 'yookassa', 'YooKassa (Legacy)'

    # External payment provider info
    external_id = models.CharField(max_length=100, unique=True, blank=True, null=True)
    provider = models.CharField(max_length=50, choices=Provider.choices, default=Provider.TOCHKA)
    confirmation_url = models.URLField(blank=True)
    order_id = models.CharField(max_length=100, blank=True, help_text='Order ID for Tochka Cyclops')

    # Related procurement (if payment is for procurement)
    procurement = models.ForeignKey(
        Procurement, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='payments'
    )

    description = models.TextField(blank=True)
    metadata = models.JSONField(default=dict)

    paid_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'payments'
        indexes = [
            models.Index(fields=['user', 'status'], name='payments_user_id_a1b2c3_idx'),
            models.Index(fields=['external_id'], name='payments_externa_d4e5f6_idx'),
            models.Index(fields=['created_at'], name='payments_created_g7h8i9_idx'),
        ]
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.payment_type} - {self.amount} - {self.status}"

    @property
    def status_display(self):
        return dict(self.Status.choices).get(self.status, self.status)


class Transaction(models.Model):
    """Internal transaction record for balance changes"""

    class TransactionType(models.TextChoices):
        DEPOSIT = 'deposit', 'Deposit'
        WITHDRAWAL = 'withdrawal', 'Withdrawal'
        PROCUREMENT_JOIN = 'procurement_join', 'Procurement Join'
        PROCUREMENT_REFUND = 'procurement_refund', 'Procurement Refund'
        TRANSFER = 'transfer', 'Transfer'
        BONUS = 'bonus', 'Bonus'

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='transactions')
    transaction_type = models.CharField(max_length=30, choices=TransactionType.choices)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    balance_after = models.DecimalField(max_digits=12, decimal_places=2)

    payment = models.ForeignKey(
        Payment, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='transactions'
    )
    procurement = models.ForeignKey(
        Procurement, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='transactions'
    )

    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'transactions'
        indexes = [
            models.Index(fields=['user', 'created_at'], name='transactio_user_id_j0k1l2_idx'),
            models.Index(fields=['transaction_type'], name='transactio_transac_m3n4o5_idx'),
        ]
        ordering = ['-created_at']

    def __str__(self):
        sign = '+' if self.amount > 0 else ''
        return f"{self.user} {sign}{self.amount} ({self.transaction_type})"

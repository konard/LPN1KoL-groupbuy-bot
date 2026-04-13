from django.contrib import admin
from .models import Payment, Transaction


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ['id', 'user', 'payment_type', 'amount', 'status', 'provider', 'paid_at', 'created_at']
    list_filter = ['payment_type', 'status', 'provider', 'created_at']
    search_fields = ['user__first_name', 'external_id', 'description']
    readonly_fields = ['external_id', 'paid_at', 'created_at', 'updated_at']


@admin.register(Transaction)
class TransactionAdmin(admin.ModelAdmin):
    list_display = ['id', 'user', 'transaction_type', 'amount', 'balance_after', 'created_at']
    list_filter = ['transaction_type', 'created_at']
    search_fields = ['user__first_name', 'description']
    readonly_fields = ['created_at']

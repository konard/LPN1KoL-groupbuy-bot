"""
Views for Payments API
Supports both Tochka Bank Cyclops and YooKassa (legacy)
"""
import logging
from decimal import Decimal
from datetime import datetime

from django.db import models
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django.conf import settings
from django.db import transaction as db_transaction
from django.utils import timezone

from .models import Payment, Transaction
from .serializers import (
    PaymentSerializer, CreatePaymentSerializer,
    TransactionSerializer
)
from users.models import User

logger = logging.getLogger(__name__)


class PaymentViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing payments.

    Endpoints:
    - GET /api/payments/ - list payments
    - POST /api/payments/ - create a payment
    - GET /api/payments/{id}/ - get payment details
    - GET /api/payments/{id}/status/ - get payment status
    - POST /api/payments/webhook/tochka/ - handle Tochka Cyclops webhook
    - POST /api/payments/webhook/yookassa/ - handle YooKassa webhook (legacy)
    """
    queryset = Payment.objects.all()
    serializer_class = PaymentSerializer

    def get_queryset(self):
        queryset = super().get_queryset()

        user_id = self.request.query_params.get('user_id')
        if user_id:
            queryset = queryset.filter(user_id=user_id)

        payment_type = self.request.query_params.get('payment_type')
        if payment_type:
            queryset = queryset.filter(payment_type=payment_type)

        payment_status = self.request.query_params.get('status')
        if payment_status:
            queryset = queryset.filter(status=payment_status)

        return queryset

    def create(self, request, *args, **kwargs):
        """Create a new payment (deposit)"""
        serializer = CreatePaymentSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        user_id = serializer.validated_data['user_id']
        amount = serializer.validated_data['amount']
        description = serializer.validated_data.get('description', f'Deposit {amount} RUB')

        # Try Tochka Bank Cyclops first, fall back to YooKassa simulation
        try:
            payment = self._create_tochka_payment(user_id, amount, description)
        except Exception as e:
            logger.warning(f"Tochka payment failed, using fallback: {e}")
            payment = self._create_fallback_payment(user_id, amount, description)

        return Response(
            PaymentSerializer(payment).data,
            status=status.HTTP_201_CREATED
        )

    def _create_tochka_payment(self, user_id: int, amount: Decimal, description: str) -> Payment:
        """Create payment via Tochka Bank Cyclops"""
        from .tochka_client import tochka_client, TochkaCyclopsError

        if not tochka_client.is_configured:
            raise TochkaCyclopsError("Tochka Cyclops is not configured")

        # Create payment record first
        payment = Payment.objects.create(
            user_id=user_id,
            payment_type=Payment.PaymentType.DEPOSIT,
            amount=amount,
            description=description,
            status=Payment.Status.PENDING,
            provider=Payment.Provider.TOCHKA
        )

        # Create deposit link via Cyclops API
        result = tochka_client.create_deposit_link(
            user_id=user_id,
            amount=amount,
            description=description,
            return_url=getattr(settings, 'PAYMENT_RETURN_URL', '')
        )

        payment.external_id = result['payment_id']
        payment.order_id = result['order_id']
        payment.confirmation_url = result['confirmation_url']
        payment.save()

        logger.info(f"Created Tochka payment {payment.id} for user {user_id}")
        return payment

    def _create_fallback_payment(self, user_id: int, amount: Decimal, description: str) -> Payment:
        """Create payment with simulated confirmation URL (for development/testing)"""
        payment = Payment.objects.create(
            user_id=user_id,
            payment_type=Payment.PaymentType.DEPOSIT,
            amount=amount,
            description=description,
            status=Payment.Status.PENDING,
            provider=Payment.Provider.YOOKASSA
        )

        # Simulate YooKassa-style confirmation URL
        payment.confirmation_url = f"https://yookassa.ru/checkout/payments/v2/contract?orderId={payment.id}"
        payment.external_id = f"yookassa_{payment.id}_{int(datetime.now().timestamp())}"
        payment.save()

        logger.info(f"Created fallback payment {payment.id} for user {user_id}")
        return payment

    @action(detail=True, methods=['get'])
    def status(self, request, pk=None):
        """Get payment status"""
        payment = self.get_object()

        # For Tochka payments, try to fetch fresh status from API
        if payment.provider == Payment.Provider.TOCHKA and payment.status == Payment.Status.PENDING:
            try:
                from .tochka_client import tochka_client
                if tochka_client.is_configured and payment.external_id:
                    result = tochka_client.get_payment_status(payment.external_id)
                    if result['status'] != payment.status:
                        self._update_payment_status(payment, result['status'], result.get('paid_at'))
            except Exception as e:
                logger.warning(f"Failed to fetch Tochka payment status: {e}")

        return Response({
            'id': payment.id,
            'status': payment.status,
            'status_display': payment.status_display,
            'amount': str(payment.amount),
            'provider': payment.provider,
            'paid_at': payment.paid_at,
            'created_at': payment.created_at
        })

    def _update_payment_status(self, payment, new_status: str, paid_at=None):
        """Update payment status and process if succeeded"""
        if new_status == Payment.Status.SUCCEEDED and payment.status != Payment.Status.SUCCEEDED:
            self._process_successful_payment(payment, {})
        elif new_status == Payment.Status.CANCELLED:
            payment.status = Payment.Status.CANCELLED
            payment.save()

    @action(detail=False, methods=['post'], url_path='webhook/tochka')
    def webhook_tochka(self, request):
        """Handle Tochka Bank Cyclops webhook"""
        try:
            from .tochka_client import tochka_client

            # Verify webhook signature
            signature = request.headers.get('X-Signature', '')
            body = request.body.decode('utf-8')

            if not tochka_client.verify_webhook_signature(body, signature):
                logger.warning("Invalid Tochka webhook signature")
                return Response(
                    {'error': 'Invalid signature'},
                    status=status.HTTP_401_UNAUTHORIZED
                )

            event_type = request.data.get('eventType', '')
            payment_data = request.data.get('payment', {})
            order_id = payment_data.get('orderId')

            if not order_id:
                return Response(
                    {'error': 'Missing order ID'},
                    status=status.HTTP_400_BAD_REQUEST
                )

            payment = Payment.objects.filter(order_id=order_id).first()
            if not payment:
                logger.warning(f"Payment not found for order {order_id}")
                return Response(
                    {'error': 'Payment not found'},
                    status=status.HTTP_404_NOT_FOUND
                )

            # Process based on event type
            if event_type in ['payment.completed', 'payment.succeeded']:
                self._process_successful_payment(payment, payment_data)
                logger.info(f"Tochka payment {payment.id} succeeded")
            elif event_type in ['payment.failed', 'payment.cancelled']:
                payment.status = Payment.Status.CANCELLED
                payment.save()
                logger.info(f"Tochka payment {payment.id} cancelled")
            elif event_type == 'payment.refunded':
                self._process_refund(payment, payment_data)
                logger.info(f"Tochka payment {payment.id} refunded")

            return Response({'status': 'ok'})

        except Exception as e:
            logger.error(f"Tochka webhook error: {e}")
            return Response(
                {'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=False, methods=['post'], url_path='webhook/yookassa')
    def webhook_yookassa(self, request):
        """Handle YooKassa webhook (legacy)"""
        try:
            event_type = request.data.get('event')
            payment_object = request.data.get('object', {})
            external_id = payment_object.get('id')

            if not external_id:
                return Response(
                    {'error': 'Missing payment ID'},
                    status=status.HTTP_400_BAD_REQUEST
                )

            payment = Payment.objects.filter(external_id=external_id).first()
            if not payment:
                return Response(
                    {'error': 'Payment not found'},
                    status=status.HTTP_404_NOT_FOUND
                )

            if event_type == 'payment.succeeded':
                self._process_successful_payment(payment, payment_object)
            elif event_type == 'payment.canceled':
                payment.status = Payment.Status.CANCELLED
                payment.save()
            elif event_type == 'refund.succeeded':
                self._process_refund(payment, payment_object)

            return Response({'status': 'ok'})

        except Exception as e:
            logger.error(f"YooKassa webhook error: {e}")
            return Response(
                {'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    # Keep legacy webhook endpoint for backwards compatibility
    @action(detail=False, methods=['post'])
    def webhook(self, request):
        """Handle webhook (auto-detect provider)"""
        # Detect provider from request
        if request.headers.get('X-Tochka-Signature') or 'orderId' in str(request.data):
            return self.webhook_tochka(request)
        else:
            return self.webhook_yookassa(request)

    @action(detail=True, methods=['post'])
    def simulate_success(self, request, pk=None):
        """Simulate successful payment (for testing)"""
        payment = self.get_object()

        if payment.status != Payment.Status.PENDING:
            return Response(
                {'error': 'Payment is not pending'},
                status=status.HTTP_400_BAD_REQUEST
            )

        self._process_successful_payment(payment, {})

        return Response({
            'status': 'success',
            'payment': PaymentSerializer(payment).data
        })

    def _process_successful_payment(self, payment, payment_object):
        """Process a successful payment"""
        from django.db.models import F
        with db_transaction.atomic():
            payment.status = Payment.Status.SUCCEEDED
            payment.paid_at = timezone.now()
            payment.save(update_fields=['status', 'paid_at', 'updated_at'])

            # Update user balance atomically using F() to avoid race conditions
            from users.models import User as UserModel
            UserModel.objects.filter(pk=payment.user_id).update(
                balance=F('balance') + payment.amount
            )
            # Refresh from DB to get the updated balance
            user = UserModel.objects.get(pk=payment.user_id)

            # Create transaction record
            Transaction.objects.create(
                user=user,
                transaction_type=Transaction.TransactionType.DEPOSIT,
                amount=payment.amount,
                balance_after=user.balance,
                payment=payment,
                description=f'Deposit: {payment.description}'
            )

    def _process_refund(self, payment, refund_object):
        """Process a refund"""
        from django.db.models import F
        with db_transaction.atomic():
            # Get refund amount from object
            if 'amount' in refund_object:
                if isinstance(refund_object['amount'], dict):
                    refund_amount = Decimal(str(refund_object['amount'].get('value', 0)))
                else:
                    refund_amount = Decimal(str(refund_object['amount']))
            else:
                refund_amount = payment.amount

            payment.status = Payment.Status.REFUNDED
            payment.save(update_fields=['status', 'updated_at'])

            # Update user balance atomically using F() to avoid race conditions
            from users.models import User as UserModel
            UserModel.objects.filter(pk=payment.user_id).update(
                balance=F('balance') - refund_amount
            )
            # Refresh from DB to get the updated balance
            user = UserModel.objects.get(pk=payment.user_id)

            # Create transaction record
            Transaction.objects.create(
                user=user,
                transaction_type=Transaction.TransactionType.WITHDRAWAL,
                amount=-refund_amount,
                balance_after=user.balance,
                payment=payment,
                description=f'Refund: {payment.description}'
            )


class TransactionViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet for viewing transactions.

    Endpoints:
    - GET /api/payments/transactions/ - list transactions
    - GET /api/payments/transactions/{id}/ - get transaction details
    - GET /api/payments/transactions/summary/ - get transaction summary
    """
    queryset = Transaction.objects.select_related('user', 'payment', 'procurement')
    serializer_class = TransactionSerializer

    def get_queryset(self):
        queryset = super().get_queryset()

        user_id = self.request.query_params.get('user_id')
        if user_id:
            queryset = queryset.filter(user_id=user_id)

        transaction_type = self.request.query_params.get('transaction_type')
        if transaction_type:
            queryset = queryset.filter(transaction_type=transaction_type)

        return queryset

    @action(detail=False, methods=['get'])
    def summary(self, request):
        """Get transaction summary for a user"""
        user_id = request.query_params.get('user_id')

        if not user_id:
            return Response(
                {'error': 'user_id is required'},
                status=status.HTTP_400_BAD_REQUEST
            )

        transactions = self.get_queryset().filter(user_id=user_id)

        # Calculate totals
        deposits = transactions.filter(
            transaction_type=Transaction.TransactionType.DEPOSIT
        ).aggregate(total=models.Sum('amount'))['total'] or 0

        withdrawals = transactions.filter(
            transaction_type__in=[
                Transaction.TransactionType.WITHDRAWAL,
                Transaction.TransactionType.PROCUREMENT_JOIN
            ]
        ).aggregate(total=models.Sum('amount'))['total'] or 0

        refunds = transactions.filter(
            transaction_type=Transaction.TransactionType.PROCUREMENT_REFUND
        ).aggregate(total=models.Sum('amount'))['total'] or 0

        user = User.objects.filter(id=user_id).first()

        return Response({
            'user_id': int(user_id),
            'current_balance': str(user.balance) if user else '0',
            'total_deposited': str(abs(deposits)),
            'total_withdrawn': str(abs(withdrawals)),
            'total_refunded': str(abs(refunds)),
            'transaction_count': transactions.count()
        })

"""
Admin API Views
Provides API endpoints for the admin panel.
"""
import logging
from datetime import timedelta
from decimal import Decimal

from django.db.models import Count, Sum, Q
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import ensure_csrf_cookie
from django.contrib.auth import authenticate, login, logout

from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.permissions import AllowAny

from users.models import User
from procurements.models import Category, Procurement
from payments.models import Payment, Transaction
from chat.models import Message, Notification

from .permissions import IsAdminUser
from .serializers import (
    DashboardStatsSerializer,
    AdminUserSerializer, AdminUserUpdateSerializer,
    AdminProcurementSerializer, AdminProcurementUpdateSerializer,
    AdminParticipantSerializer,
    AdminPaymentSerializer, AdminTransactionSerializer,
    AdminCategorySerializer,
    AdminMessageSerializer, AdminNotificationSerializer,
    AdminLoginSerializer, AdminUserInfoSerializer,
    BulkActionSerializer
)

logger = logging.getLogger(__name__)


@method_decorator(ensure_csrf_cookie, name='dispatch')
class AdminAuthView(APIView):
    """Admin authentication endpoints."""
    permission_classes = [AllowAny]

    def get(self, request):
        """Check if user is authenticated as admin."""
        if request.user.is_authenticated and request.user.is_staff:
            serializer = AdminUserInfoSerializer({
                'id': request.user.id,
                'username': request.user.username,
                'email': request.user.email,
                'is_staff': request.user.is_staff,
                'is_superuser': request.user.is_superuser,
            })
            return Response(serializer.data)
        return Response({'detail': 'Not authenticated'}, status=status.HTTP_401_UNAUTHORIZED)

    def post(self, request):
        """Login as admin."""
        serializer = AdminLoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        user = authenticate(
            request,
            username=serializer.validated_data['username'],
            password=serializer.validated_data['password']
        )

        if user is not None and user.is_staff:
            login(request, user)
            logger.info(f"Admin user logged in: {user.username}")
            return Response({
                'id': user.id,
                'username': user.username,
                'email': user.email,
                'is_staff': user.is_staff,
                'is_superuser': user.is_superuser,
            })
        return Response(
            {'detail': 'Invalid credentials or not an admin user'},
            status=status.HTTP_401_UNAUTHORIZED
        )

    def delete(self, request):
        """Logout."""
        if request.user.is_authenticated:
            logger.info(f"Admin user logged out: {request.user.username}")
            logout(request)
        return Response({'detail': 'Logged out'})


class DashboardView(APIView):
    """Dashboard statistics endpoint."""
    permission_classes = [IsAdminUser]

    def get(self, request):
        """Get dashboard statistics."""
        now = timezone.now()
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        week_start = today_start - timedelta(days=7)
        month_start = today_start - timedelta(days=30)

        # User statistics
        total_users = User.objects.count()
        users_by_role = dict(
            User.objects.values_list('role').annotate(count=Count('id'))
        )
        users_by_platform = dict(
            User.objects.values_list('platform').annotate(count=Count('id'))
        )
        new_users_today = User.objects.filter(created_at__gte=today_start).count()
        new_users_week = User.objects.filter(created_at__gte=week_start).count()
        new_users_month = User.objects.filter(created_at__gte=month_start).count()

        # Procurement statistics
        total_procurements = Procurement.objects.count()
        procurements_by_status = dict(
            Procurement.objects.values_list('status').annotate(count=Count('id'))
        )
        active_procurements = Procurement.objects.filter(status='active').count()
        completed_procurements = Procurement.objects.filter(status='completed').count()

        # Payment statistics
        total_payments = Payment.objects.count()
        payments_by_status = dict(
            Payment.objects.values_list('status').annotate(count=Count('id'))
        )

        succeeded_payments = Payment.objects.filter(status='succeeded')
        total_revenue = succeeded_payments.aggregate(
            total=Sum('amount')
        )['total'] or Decimal('0')
        revenue_today = succeeded_payments.filter(
            paid_at__gte=today_start
        ).aggregate(total=Sum('amount'))['total'] or Decimal('0')
        revenue_week = succeeded_payments.filter(
            paid_at__gte=week_start
        ).aggregate(total=Sum('amount'))['total'] or Decimal('0')
        revenue_month = succeeded_payments.filter(
            paid_at__gte=month_start
        ).aggregate(total=Sum('amount'))['total'] or Decimal('0')

        # Message statistics
        total_messages = Message.objects.count()
        messages_today = Message.objects.filter(created_at__gte=today_start).count()

        stats = {
            'total_users': total_users,
            'users_by_role': users_by_role,
            'users_by_platform': users_by_platform,
            'new_users_today': new_users_today,
            'new_users_week': new_users_week,
            'new_users_month': new_users_month,

            'total_procurements': total_procurements,
            'procurements_by_status': procurements_by_status,
            'active_procurements': active_procurements,
            'completed_procurements': completed_procurements,

            'total_payments': total_payments,
            'payments_by_status': payments_by_status,
            'total_revenue': total_revenue,
            'revenue_today': revenue_today,
            'revenue_week': revenue_week,
            'revenue_month': revenue_month,

            'total_messages': total_messages,
            'messages_today': messages_today,
        }

        serializer = DashboardStatsSerializer(stats)
        response = Response(serializer.data)
        # Allow private caching for 30 seconds to reduce DB load when the
        # frontend polls; cache is private so only the user's browser caches it.
        response['Cache-Control'] = 'private, max-age=30'
        return response


class AnalyticsView(APIView):
    """Advanced analytics endpoint with date range filtering."""
    permission_classes = [IsAdminUser]

    def get(self, request):
        """Get analytics data with optional date filtering."""
        from datetime import datetime
        from django.db.models.functions import TruncDate, TruncWeek, TruncMonth
        from procurements.models import Participant

        params = request.query_params
        now = timezone.now()

        # Parse date range
        date_from_str = params.get('date_from')
        date_to_str = params.get('date_to')
        period = params.get('period', 'day')  # day, week, month

        if date_from_str:
            try:
                date_from = datetime.strptime(date_from_str, '%Y-%m-%d')
                date_from = timezone.make_aware(date_from)
            except ValueError:
                date_from = now - timedelta(days=30)
        else:
            date_from = now - timedelta(days=30)

        if date_to_str:
            try:
                date_to = datetime.strptime(date_to_str, '%Y-%m-%d')
                date_to = timezone.make_aware(date_to).replace(
                    hour=23, minute=59, second=59
                )
            except ValueError:
                date_to = now
        else:
            date_to = now

        # Choose truncation function based on period
        trunc_fn = {
            'day': TruncDate,
            'week': TruncWeek,
            'month': TruncMonth,
        }.get(period, TruncDate)

        # Time series: user registrations
        user_series = list(
            User.objects.filter(
                created_at__gte=date_from, created_at__lte=date_to
            ).annotate(
                date=trunc_fn('created_at')
            ).values('date').annotate(
                count=Count('id')
            ).order_by('date')
        )

        # Time series: revenue
        revenue_series = list(
            Payment.objects.filter(
                status='succeeded',
                paid_at__gte=date_from,
                paid_at__lte=date_to,
            ).annotate(
                date=trunc_fn('paid_at')
            ).values('date').annotate(
                total=Sum('amount'),
                count=Count('id')
            ).order_by('date')
        )

        # Time series: procurements created
        procurement_series = list(
            Procurement.objects.filter(
                created_at__gte=date_from, created_at__lte=date_to
            ).annotate(
                date=trunc_fn('created_at')
            ).values('date').annotate(
                count=Count('id')
            ).order_by('date')
        )

        # Time series: messages sent
        message_series = list(
            Message.objects.filter(
                created_at__gte=date_from, created_at__lte=date_to
            ).annotate(
                date=trunc_fn('created_at')
            ).values('date').annotate(
                count=Count('id')
            ).order_by('date')
        )

        # Top categories
        top_categories = list(
            Category.objects.annotate(
                procurement_count=Count('procurements')
            ).order_by('-procurement_count')[:10].values(
                'id', 'name', 'icon', 'procurement_count'
            )
        )

        # Top organizers
        top_organizers = list(
            User.objects.filter(role='organizer').annotate(
                procurement_count=Count('organized_procurements')
            ).order_by('-procurement_count')[:10].values(
                'id', 'first_name', 'last_name', 'procurement_count'
            )
        )

        # Conversion funnel
        total_users = User.objects.filter(
            created_at__gte=date_from, created_at__lte=date_to
        ).count()
        users_participated = Participant.objects.filter(
            created_at__gte=date_from, created_at__lte=date_to
        ).values('user').distinct().count()
        users_paid = Payment.objects.filter(
            status='succeeded',
            created_at__gte=date_from,
            created_at__lte=date_to,
        ).values('user').distinct().count()

        # Serialize dates to strings
        def serialize_series(series, value_key='count'):
            result = []
            for item in series:
                d = item.get('date')
                date_str = d.isoformat() if d else None
                entry = {'date': date_str, value_key: item[value_key]}
                if 'total' in item:
                    entry['total'] = float(item['total'] or 0)
                result.append(entry)
            return result

        return Response({
            'date_from': date_from.isoformat(),
            'date_to': date_to.isoformat(),
            'period': period,
            'user_registrations': serialize_series(user_series),
            'revenue': serialize_series(revenue_series),
            'procurements_created': serialize_series(procurement_series),
            'messages_sent': serialize_series(message_series),
            'top_categories': top_categories,
            'top_organizers': top_organizers,
            'funnel': {
                'registered': total_users,
                'participated': users_participated,
                'paid': users_paid,
            },
        })


class AdminUserViewSet(viewsets.ModelViewSet):
    """Admin viewset for User management."""
    queryset = User.objects.all().order_by('-created_at')
    permission_classes = [IsAdminUser]

    def get_serializer_class(self):
        if self.action in ['update', 'partial_update']:
            return AdminUserUpdateSerializer
        return AdminUserSerializer

    def get_queryset(self):
        queryset = super().get_queryset()
        params = self.request.query_params

        # Filter by role
        role = params.get('role')
        if role:
            queryset = queryset.filter(role=role)

        # Filter by platform
        platform = params.get('platform')
        if platform:
            queryset = queryset.filter(platform=platform)

        # Filter by status
        is_active = params.get('is_active')
        if is_active is not None:
            queryset = queryset.filter(is_active=is_active.lower() == 'true')

        is_verified = params.get('is_verified')
        if is_verified is not None:
            queryset = queryset.filter(is_verified=is_verified.lower() == 'true')

        # Search
        search = params.get('search')
        if search:
            queryset = queryset.filter(
                Q(first_name__icontains=search) |
                Q(last_name__icontains=search) |
                Q(username__icontains=search) |
                Q(email__icontains=search) |
                Q(phone__icontains=search) |
                Q(platform_user_id__icontains=search)
            )

        return queryset

    @action(detail=True, methods=['post'])
    def toggle_active(self, request, pk=None):
        """Toggle user active status."""
        user = self.get_object()
        user.is_active = not user.is_active
        user.save(update_fields=['is_active', 'updated_at'])
        logger.info(f"Admin toggled user active status: user={user.id}, is_active={user.is_active}")
        return Response({'is_active': user.is_active})

    @action(detail=True, methods=['post'])
    def toggle_verified(self, request, pk=None):
        """Toggle user verified status."""
        user = self.get_object()
        user.is_verified = not user.is_verified
        user.save(update_fields=['is_verified', 'updated_at'])
        logger.info(f"Admin toggled user verified status: user={user.id}, is_verified={user.is_verified}")
        return Response({'is_verified': user.is_verified})

    @action(detail=True, methods=['post'])
    def update_balance(self, request, pk=None):
        """Update user balance (admin only)."""
        user = self.get_object()
        amount = request.data.get('amount')
        if amount is None:
            return Response(
                {'detail': 'Amount is required'},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            amount = Decimal(str(amount))
        except (ValueError, TypeError):
            return Response(
                {'detail': 'Invalid amount'},
                status=status.HTTP_400_BAD_REQUEST
            )

        description = request.data.get('description', 'Admin balance adjustment')
        old_balance = user.balance
        new_balance = user.update_balance(amount)

        # Create transaction record
        Transaction.objects.create(
            user=user,
            transaction_type='bonus' if amount > 0 else 'withdrawal',
            amount=amount,
            balance_after=new_balance,
            description=description
        )

        logger.info(
            f"Admin updated user balance: user={user.id}, "
            f"old_balance={old_balance}, new_balance={new_balance}, amount={amount}"
        )

        return Response({
            'old_balance': str(old_balance),
            'new_balance': str(new_balance),
            'amount': str(amount)
        })

    @action(detail=False, methods=['post'])
    def bulk_action(self, request):
        """Perform bulk action on users."""
        serializer = BulkActionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        ids = serializer.validated_data['ids']
        action_type = serializer.validated_data['action']

        users = User.objects.filter(id__in=ids)
        count = users.count()

        if action_type == 'activate':
            users.update(is_active=True)
        elif action_type == 'deactivate':
            users.update(is_active=False)
        elif action_type == 'verify':
            users.update(is_verified=True)
        elif action_type == 'unverify':
            users.update(is_verified=False)
        else:
            return Response(
                {'detail': f'Unknown action: {action_type}'},
                status=status.HTTP_400_BAD_REQUEST
            )

        logger.info(f"Admin bulk action on users: action={action_type}, count={count}")
        return Response({'affected': count})


class AdminProcurementViewSet(viewsets.ModelViewSet):
    """Admin viewset for Procurement management."""
    queryset = Procurement.objects.all().order_by('-created_at')
    permission_classes = [IsAdminUser]

    def get_serializer_class(self):
        if self.action in ['update', 'partial_update']:
            return AdminProcurementUpdateSerializer
        return AdminProcurementSerializer

    def get_queryset(self):
        queryset = super().get_queryset()
        params = self.request.query_params

        # Filter by status
        status_filter = params.get('status')
        if status_filter:
            queryset = queryset.filter(status=status_filter)

        # Filter by category
        category = params.get('category')
        if category:
            queryset = queryset.filter(category_id=category)

        # Filter by city
        city = params.get('city')
        if city:
            queryset = queryset.filter(city__icontains=city)

        # Filter by featured
        is_featured = params.get('is_featured')
        if is_featured is not None:
            queryset = queryset.filter(is_featured=is_featured.lower() == 'true')

        # Search
        search = params.get('search')
        if search:
            queryset = queryset.filter(
                Q(title__icontains=search) |
                Q(description__icontains=search) |
                Q(organizer__first_name__icontains=search)
            )

        return queryset

    @action(detail=True, methods=['post'])
    def update_status(self, request, pk=None):
        """Update procurement status."""
        procurement = self.get_object()
        new_status = request.data.get('status')

        if new_status not in dict(Procurement.Status.choices):
            return Response(
                {'detail': f'Invalid status: {new_status}'},
                status=status.HTTP_400_BAD_REQUEST
            )

        old_status = procurement.status
        procurement.status = new_status
        procurement.save(update_fields=['status', 'updated_at'])

        logger.info(
            f"Admin updated procurement status: id={procurement.id}, "
            f"old_status={old_status}, new_status={new_status}"
        )

        return Response({
            'old_status': old_status,
            'new_status': new_status
        })

    @action(detail=True, methods=['post'])
    def toggle_featured(self, request, pk=None):
        """Toggle procurement featured status."""
        procurement = self.get_object()
        procurement.is_featured = not procurement.is_featured
        procurement.save(update_fields=['is_featured', 'updated_at'])
        logger.info(f"Admin toggled procurement featured: id={procurement.id}, is_featured={procurement.is_featured}")
        return Response({'is_featured': procurement.is_featured})

    @action(detail=True)
    def participants(self, request, pk=None):
        """Get participants for a procurement."""
        procurement = self.get_object()
        participants = procurement.participants.all().order_by('-created_at')
        serializer = AdminParticipantSerializer(participants, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['post'])
    def bulk_action(self, request):
        """Perform bulk action on procurements."""
        serializer = BulkActionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        ids = serializer.validated_data['ids']
        action_type = serializer.validated_data['action']

        procurements = Procurement.objects.filter(id__in=ids)
        count = procurements.count()

        if action_type == 'feature':
            procurements.update(is_featured=True)
        elif action_type == 'unfeature':
            procurements.update(is_featured=False)
        elif action_type in dict(Procurement.Status.choices):
            procurements.update(status=action_type)
        else:
            return Response(
                {'detail': f'Unknown action: {action_type}'},
                status=status.HTTP_400_BAD_REQUEST
            )

        logger.info(f"Admin bulk action on procurements: action={action_type}, count={count}")
        return Response({'affected': count})


class AdminPaymentViewSet(viewsets.ReadOnlyModelViewSet):
    """Admin viewset for Payment viewing (read-only)."""
    queryset = Payment.objects.all().order_by('-created_at')
    serializer_class = AdminPaymentSerializer
    permission_classes = [IsAdminUser]

    def get_queryset(self):
        queryset = super().get_queryset()
        params = self.request.query_params

        # Filter by status
        status_filter = params.get('status')
        if status_filter:
            queryset = queryset.filter(status=status_filter)

        # Filter by type
        payment_type = params.get('payment_type')
        if payment_type:
            queryset = queryset.filter(payment_type=payment_type)

        # Filter by user
        user_id = params.get('user')
        if user_id:
            queryset = queryset.filter(user_id=user_id)

        # Date range
        date_from = params.get('date_from')
        if date_from:
            queryset = queryset.filter(created_at__date__gte=date_from)

        date_to = params.get('date_to')
        if date_to:
            queryset = queryset.filter(created_at__date__lte=date_to)

        # Search
        search = params.get('search')
        if search:
            queryset = queryset.filter(
                Q(external_id__icontains=search) |
                Q(description__icontains=search) |
                Q(user__first_name__icontains=search)
            )

        return queryset

    @action(detail=False)
    def summary(self, request):
        """Get payment summary statistics."""
        queryset = self.get_queryset()

        total = queryset.aggregate(
            count=Count('id'),
            total_amount=Sum('amount')
        )

        by_status = {
            row['status']: {'count': row['count'], 'total': row['total']}
            for row in queryset.values('status').annotate(
                count=Count('id'),
                total=Sum('amount')
            )
        }

        by_type = {
            row['payment_type']: {'count': row['count'], 'total': row['total']}
            for row in queryset.values('payment_type').annotate(
                count=Count('id'),
                total=Sum('amount')
            )
        }

        return Response({
            'total_count': total['count'],
            'total_amount': total['total_amount'] or 0,
            'by_status': by_status,
            'by_type': by_type,
        })


class AdminTransactionViewSet(viewsets.ReadOnlyModelViewSet):
    """Admin viewset for Transaction viewing (read-only)."""
    queryset = Transaction.objects.all().order_by('-created_at')
    serializer_class = AdminTransactionSerializer
    permission_classes = [IsAdminUser]

    def get_queryset(self):
        queryset = super().get_queryset()
        params = self.request.query_params

        # Filter by type
        transaction_type = params.get('transaction_type')
        if transaction_type:
            queryset = queryset.filter(transaction_type=transaction_type)

        # Filter by user
        user_id = params.get('user')
        if user_id:
            queryset = queryset.filter(user_id=user_id)

        # Date range
        date_from = params.get('date_from')
        if date_from:
            queryset = queryset.filter(created_at__date__gte=date_from)

        date_to = params.get('date_to')
        if date_to:
            queryset = queryset.filter(created_at__date__lte=date_to)

        return queryset


class AdminCategoryViewSet(viewsets.ModelViewSet):
    """Admin viewset for Category management."""
    queryset = Category.objects.all().order_by('name')
    serializer_class = AdminCategorySerializer
    permission_classes = [IsAdminUser]


class AdminMessageViewSet(viewsets.ModelViewSet):
    """Admin viewset for Message management."""
    queryset = Message.objects.all().order_by('-created_at')
    serializer_class = AdminMessageSerializer
    permission_classes = [IsAdminUser]

    def get_queryset(self):
        queryset = super().get_queryset()
        params = self.request.query_params

        # Filter by procurement
        procurement_id = params.get('procurement')
        if procurement_id:
            queryset = queryset.filter(procurement_id=procurement_id)

        # Filter by user
        user_id = params.get('user')
        if user_id:
            queryset = queryset.filter(user_id=user_id)

        # Search
        search = params.get('search')
        if search:
            queryset = queryset.filter(text__icontains=search)

        return queryset

    @action(detail=True, methods=['post'])
    def toggle_delete(self, request, pk=None):
        """Toggle message deleted status."""
        message = self.get_object()
        message.is_deleted = not message.is_deleted
        message.save(update_fields=['is_deleted', 'updated_at'])
        logger.info(f"Admin toggled message deleted: id={message.id}, is_deleted={message.is_deleted}")
        return Response({'is_deleted': message.is_deleted})


class AdminChatMessageView(APIView):
    """Send a direct admin message to a user as a system notification."""
    permission_classes = [IsAdminUser]

    def post(self, request):
        """Create a system notification to deliver an admin message to a user."""
        user_id = request.data.get('user_id')
        text = request.data.get('text')

        if not user_id or not text:
            return Response(
                {'detail': 'user_id and text are required'},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            user = User.objects.get(id=user_id)
        except User.DoesNotExist:
            return Response(
                {'detail': 'User not found'},
                status=status.HTTP_404_NOT_FOUND
            )

        notification = Notification.objects.create(
            user=user,
            notification_type='admin_message',
            title='Сообщение от администратора',
            message=text
        )

        logger.info(f"Admin sent message to user {user_id}: {text[:50]}")
        return Response({
            'id': notification.id,
            'user_id': user_id,
            'text': text,
        }, status=status.HTTP_201_CREATED)


class AdminNotificationViewSet(viewsets.ModelViewSet):
    """Admin viewset for Notification management."""
    queryset = Notification.objects.all().order_by('-created_at')
    serializer_class = AdminNotificationSerializer
    permission_classes = [IsAdminUser]

    def get_queryset(self):
        queryset = super().get_queryset()
        params = self.request.query_params

        # Filter by user
        user_id = params.get('user')
        if user_id:
            queryset = queryset.filter(user_id=user_id)

        # Filter by type
        notification_type = params.get('notification_type')
        if notification_type:
            queryset = queryset.filter(notification_type=notification_type)

        return queryset

    @action(detail=False, methods=['post'])
    def send_bulk(self, request):
        """Send notification to multiple users."""
        user_ids = request.data.get('user_ids', [])
        notification_type = request.data.get('notification_type', 'system')
        title = request.data.get('title')
        message_text = request.data.get('message')

        if not title or not message_text:
            return Response(
                {'detail': 'Title and message are required'},
                status=status.HTTP_400_BAD_REQUEST
            )

        notifications = []
        if user_ids:
            users = User.objects.filter(id__in=user_ids)
        else:
            # Send to all active users
            users = User.objects.filter(is_active=True)

        for user in users:
            notifications.append(Notification(
                user=user,
                notification_type=notification_type,
                title=title,
                message=message_text
            ))

        Notification.objects.bulk_create(notifications)
        logger.info(f"Admin sent bulk notification: count={len(notifications)}")
        return Response({'sent': len(notifications)})

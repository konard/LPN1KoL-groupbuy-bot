"""
Views for User API
"""
import os
import time

import jwt
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django.shortcuts import get_object_or_404
from django.db.models import Sum

from .models import User, UserSession
from .serializers import (
    UserSerializer, UserRegistrationSerializer, UserProfileUpdateSerializer,
    UserBalanceSerializer, UserSessionSerializer
)

# Token lifetime for WebSocket authentication tokens (24 hours)
_WS_TOKEN_TTL = 86400


class UserViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing users.

    Endpoints:
    - GET /api/users/ - list all users
    - GET /api/users/?role=supplier - filter by role
    - POST /api/users/ - create new user (register)
    - GET /api/users/{id}/ - get user details
    - PUT /api/users/{id}/ - update user
    - DELETE /api/users/{id}/ - delete user
    - GET /api/users/by_platform/ - get user by platform and platform_user_id
    - GET /api/users/{id}/balance/ - get user balance
    - POST /api/users/{id}/update_balance/ - update user balance
    - GET /api/users/{id}/role/ - get user role
    """
    queryset = User.objects.all()
    serializer_class = UserSerializer

    def get_serializer_class(self):
        if self.action == 'create':
            return UserRegistrationSerializer
        if self.action in ['update', 'partial_update']:
            return UserProfileUpdateSerializer
        return UserSerializer

    def get_queryset(self):
        queryset = super().get_queryset()
        role = self.request.query_params.get('role')
        if role:
            queryset = queryset.filter(role=role)
        platform = self.request.query_params.get('platform')
        if platform:
            queryset = queryset.filter(platform=platform)
        return queryset

    @action(detail=False, methods=['get'])
    def by_platform(self, request):
        """Get user by platform and platform_user_id"""
        platform = request.query_params.get('platform', 'telegram')
        platform_user_id = request.query_params.get('platform_user_id')

        if not platform_user_id:
            return Response(
                {'error': 'platform_user_id is required'},
                status=status.HTTP_400_BAD_REQUEST
            )

        user = get_object_or_404(
            User,
            platform=platform,
            platform_user_id=platform_user_id
        )
        serializer = self.get_serializer(user)
        return Response(serializer.data)

    @action(detail=False, methods=['get'])
    def by_email(self, request):
        """Get user by email address"""
        email = request.query_params.get('email')

        if not email:
            return Response(
                {'error': 'email is required'},
                status=status.HTTP_400_BAD_REQUEST
            )

        user = get_object_or_404(User, email__iexact=email)
        serializer = self.get_serializer(user)
        return Response(serializer.data)

    @action(detail=False, methods=['get'])
    def by_phone(self, request):
        """Get user by phone number"""
        phone = request.query_params.get('phone')

        if not phone:
            return Response(
                {'error': 'phone is required'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Normalize phone: ensure it starts with +
        if phone and not phone.startswith('+'):
            phone = '+' + phone

        user = get_object_or_404(User, phone=phone)
        serializer = self.get_serializer(user)
        return Response(serializer.data)

    @action(detail=False, methods=['get'])
    def search(self, request):
        """Search users by name, username, email, or phone (for personal cabinet user search)."""
        query = request.query_params.get('q', '').strip()
        if not query:
            return Response(
                {'error': 'q (search query) is required'},
                status=status.HTTP_400_BAD_REQUEST
            )

        from django.db.models import Q
        users = self.get_queryset().filter(
            Q(first_name__icontains=query) |
            Q(last_name__icontains=query) |
            Q(username__icontains=query) |
            Q(email__icontains=query) |
            Q(phone__icontains=query)
        )[:20]

        serializer = self.get_serializer(users, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['get'])
    def check_exists(self, request):
        """Check if user exists by platform and platform_user_id"""
        platform = request.query_params.get('platform', 'telegram')
        platform_user_id = request.query_params.get('platform_user_id')

        if not platform_user_id:
            return Response(
                {'error': 'platform_user_id is required'},
                status=status.HTTP_400_BAD_REQUEST
            )

        exists = User.objects.filter(
            platform=platform,
            platform_user_id=platform_user_id
        ).exists()

        return Response({'exists': exists})

    @action(detail=True, methods=['get'])
    def balance(self, request, pk=None):
        """Get user balance with statistics"""
        from payments.models import Transaction
        user = self.get_object()

        # Calculate totals from Transaction records
        deposits = user.transactions.filter(
            transaction_type=Transaction.TransactionType.DEPOSIT
        ).aggregate(total=Sum('amount'))['total'] or 0

        spent = user.transactions.filter(
            transaction_type__in=[
                Transaction.TransactionType.WITHDRAWAL,
                Transaction.TransactionType.PROCUREMENT_JOIN,
            ]
        ).aggregate(total=Sum('amount'))['total'] or 0

        data = {
            'balance': user.balance,
            'total_deposited': abs(deposits),
            'total_spent': abs(spent),
            'available': user.balance,
        }
        serializer = UserBalanceSerializer(data)
        return Response(serializer.data)

    @action(detail=True, methods=['post'])
    def update_balance(self, request, pk=None):
        """Update user balance"""
        user = self.get_object()
        amount = request.data.get('amount')

        if amount is None:
            return Response(
                {'error': 'amount is required'},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            amount = float(amount)
        except (ValueError, TypeError):
            return Response(
                {'error': 'amount must be a number'},
                status=status.HTTP_400_BAD_REQUEST
            )

        new_balance = user.update_balance(amount)
        return Response({
            'balance': new_balance,
            'message': 'Balance updated successfully'
        })

    @action(detail=True, methods=['get'])
    def role(self, request, pk=None):
        """Get user role"""
        user = self.get_object()
        return Response({
            'role': user.role,
            'role_display': user.role_display
        })

    @action(detail=True, methods=['get'])
    def ws_token(self, request, pk=None):
        """Generate a short-lived JWT for WebSocket authentication.

        The WebSocket server (infrastructure/websocket/chat_server.py) validates
        this token via the shared JWT_SECRET environment variable.  The token
        expires after 24 hours; the frontend should refresh it on next page load.

        Returns:
            {"token": "<JWT>", "expires_in": 86400}
        """
        user = self.get_object()
        secret = os.environ.get('JWT_SECRET', 'your-secret-key')
        now = int(time.time())
        payload = {
            'user_id': user.id,
            'iat': now,
            'exp': now + _WS_TOKEN_TTL,
        }
        token = jwt.encode(payload, secret, algorithm='HS256')
        # PyJWT ≥ 2.0 returns str; older versions return bytes
        if isinstance(token, bytes):
            token = token.decode('utf-8')
        return Response({'token': token, 'expires_in': _WS_TOKEN_TTL})


class UserSessionViewSet(viewsets.ModelViewSet):
    """ViewSet for managing user sessions"""
    queryset = UserSession.objects.all()
    serializer_class = UserSessionSerializer

    def get_queryset(self):
        user_id = self.request.query_params.get('user_id')
        if user_id:
            return self.queryset.filter(user_id=user_id)
        return self.queryset

    @action(detail=False, methods=['post'])
    def set_state(self, request):
        """Set or update dialog state for a user"""
        user_id = request.data.get('user_id')
        dialog_type = request.data.get('dialog_type', '')
        dialog_state = request.data.get('dialog_state', '')
        dialog_data = request.data.get('dialog_data', {})

        if not user_id:
            return Response(
                {'error': 'user_id is required'},
                status=status.HTTP_400_BAD_REQUEST
            )

        session, created = UserSession.objects.update_or_create(
            user_id=user_id,
            defaults={
                'dialog_type': dialog_type,
                'dialog_state': dialog_state,
                'dialog_data': dialog_data,
            }
        )

        serializer = self.get_serializer(session)
        return Response(serializer.data)

    @action(detail=False, methods=['post'])
    def clear_state(self, request):
        """Clear dialog state for a user"""
        user_id = request.data.get('user_id')

        if not user_id:
            return Response(
                {'error': 'user_id is required'},
                status=status.HTTP_400_BAD_REQUEST
            )

        UserSession.objects.filter(user_id=user_id).delete()
        return Response({'message': 'Session cleared'})

"""
Views for Chat API
"""
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response

from .models import Message, MessageRead, Notification
from .serializers import (
    MessageSerializer, CreateMessageSerializer,
    NotificationSerializer
)


class MessageViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing chat messages.

    Endpoints:
    - GET /api/chat/messages/ - list messages (requires procurement_id)
    - POST /api/chat/messages/ - create a message
    - GET /api/chat/messages/{id}/ - get message details
    - POST /api/chat/messages/mark_read/ - mark messages as read
    - GET /api/chat/messages/unread_count/ - get unread message count
    """
    queryset = Message.objects.filter(is_deleted=False).select_related('user')
    serializer_class = MessageSerializer

    def get_queryset(self):
        queryset = super().get_queryset()

        # Filter by procurement
        procurement_id = self.request.query_params.get('procurement_id')
        if procurement_id:
            queryset = queryset.filter(procurement_id=procurement_id)

        return queryset

    def create(self, request, *args, **kwargs):
        """Create a new message"""
        serializer = CreateMessageSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        message = Message.objects.create(
            procurement_id=serializer.validated_data['procurement_id'],
            user_id=serializer.validated_data['user_id'],
            text=serializer.validated_data['text'],
            message_type=serializer.validated_data['message_type'],
            attachment_url=serializer.validated_data.get('attachment_url', '')
        )

        return Response(
            MessageSerializer(message).data,
            status=status.HTTP_201_CREATED
        )

    @action(detail=False, methods=['post'])
    def mark_read(self, request):
        """Mark messages as read"""
        user_id = request.data.get('user_id')
        procurement_id = request.data.get('procurement_id')
        message_id = request.data.get('message_id')

        if not user_id or not procurement_id:
            return Response(
                {'error': 'user_id and procurement_id are required'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Get the last message if not specified
        if not message_id:
            last_message = Message.objects.filter(
                procurement_id=procurement_id,
                is_deleted=False
            ).order_by('-created_at').first()
            message_id = last_message.id if last_message else None

        if message_id:
            MessageRead.objects.update_or_create(
                user_id=user_id,
                procurement_id=procurement_id,
                defaults={'last_read_message_id': message_id}
            )

        return Response({'message': 'Marked as read'})

    @action(detail=False, methods=['get'])
    def unread_count(self, request):
        """Get unread message count for a user"""
        user_id = request.query_params.get('user_id')
        procurement_id = request.query_params.get('procurement_id')

        if not user_id:
            return Response(
                {'error': 'user_id is required'},
                status=status.HTTP_400_BAD_REQUEST
            )

        if procurement_id:
            # Get unread count for specific procurement
            read_status = MessageRead.objects.filter(
                user_id=user_id,
                procurement_id=procurement_id
            ).first()

            if read_status and read_status.last_read_message:
                unread_count = Message.objects.filter(
                    procurement_id=procurement_id,
                    is_deleted=False,
                    created_at__gt=read_status.last_read_message.created_at
                ).exclude(user_id=user_id).count()
            else:
                unread_count = Message.objects.filter(
                    procurement_id=procurement_id,
                    is_deleted=False
                ).exclude(user_id=user_id).count()

            return Response({
                'procurement_id': int(procurement_id),
                'unread_count': unread_count
            })
        else:
            # Get unread counts for all procurements
            # This is a simplified version - in production, use raw SQL for efficiency
            return Response({'error': 'procurement_id is recommended'})


class NotificationViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing notifications.

    Endpoints:
    - GET /api/chat/notifications/ - list notifications (requires user_id)
    - POST /api/chat/notifications/ - create a notification
    - POST /api/chat/notifications/{id}/mark_read/ - mark as read
    - POST /api/chat/notifications/mark_all_read/ - mark all as read
    """
    queryset = Notification.objects.all()
    serializer_class = NotificationSerializer

    def get_queryset(self):
        user_id = self.request.query_params.get('user_id')
        if not user_id:
            return Notification.objects.none()

        # Validate that user_id is an integer (Django User pk).
        # A UUID or any non-integer value would raise ValueError inside the ORM
        # and be converted to a 400 response by DRF, so we guard against it here.
        try:
            user_id = int(user_id)
        except (ValueError, TypeError):
            return Notification.objects.none()

        queryset = Notification.objects.filter(user_id=user_id)

        unread_only = self.request.query_params.get('unread_only')
        if unread_only and unread_only.lower() == 'true':
            queryset = queryset.filter(is_read=False)

        return queryset

    @action(detail=True, methods=['post'], url_path='mark_read')
    def mark_read(self, request, pk=None):
        """Mark a notification as read"""
        notification = self.get_object()
        notification.is_read = True
        notification.save(update_fields=['is_read'])
        return Response(NotificationSerializer(notification).data)

    @action(detail=False, methods=['post'])
    def mark_all_read(self, request):
        """Mark all notifications as read for a user"""
        user_id = request.data.get('user_id')

        if not user_id:
            return Response(
                {'error': 'user_id is required'},
                status=status.HTTP_400_BAD_REQUEST
            )

        updated = Notification.objects.filter(
            user_id=user_id,
            is_read=False
        ).update(is_read=True)

        return Response({
            'message': f'Marked {updated} notifications as read'
        })

    @action(detail=False, methods=['post'])
    def send(self, request):
        """Send a notification to a user"""
        user_id = request.data.get('user_id')
        notification_type = request.data.get('notification_type')
        title = request.data.get('title')
        message = request.data.get('message')
        procurement_id = request.data.get('procurement_id')

        if not all([user_id, notification_type, title, message]):
            return Response(
                {'error': 'user_id, notification_type, title, and message are required'},
                status=status.HTTP_400_BAD_REQUEST
            )

        notification = Notification.objects.create(
            user_id=user_id,
            notification_type=notification_type,
            title=title,
            message=message,
            procurement_id=procurement_id
        )

        return Response(
            NotificationSerializer(notification).data,
            status=status.HTTP_201_CREATED
        )

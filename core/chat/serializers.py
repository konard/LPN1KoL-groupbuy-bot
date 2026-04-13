"""
Serializers for Chat API
"""
from rest_framework import serializers
from .models import Message, MessageRead, Notification


class MessageSerializer(serializers.ModelSerializer):
    """Message serializer"""
    user_name = serializers.CharField(source='user.full_name', read_only=True)

    class Meta:
        model = Message
        fields = [
            'id', 'procurement', 'user', 'user_name',
            'message_type', 'text', 'attachment_url',
            'is_edited', 'is_deleted', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'is_edited', 'is_deleted', 'created_at', 'updated_at']


class CreateMessageSerializer(serializers.Serializer):
    """Serializer for creating messages"""
    procurement_id = serializers.IntegerField()
    user_id = serializers.IntegerField()
    text = serializers.CharField()
    message_type = serializers.ChoiceField(
        choices=Message.MessageType.choices,
        default=Message.MessageType.TEXT
    )
    attachment_url = serializers.URLField(required=False, allow_blank=True)


class MessageReadSerializer(serializers.ModelSerializer):
    """Message read status serializer"""

    class Meta:
        model = MessageRead
        fields = ['user', 'procurement', 'last_read_message', 'last_read_at']


class NotificationSerializer(serializers.ModelSerializer):
    """Notification serializer"""
    procurement_title = serializers.CharField(source='procurement.title', read_only=True)

    class Meta:
        model = Notification
        fields = [
            'id', 'notification_type', 'title', 'message',
            'procurement', 'procurement_title', 'is_read', 'created_at'
        ]
        read_only_fields = ['id', 'created_at']


class UnreadCountSerializer(serializers.Serializer):
    """Serializer for unread message count"""
    procurement_id = serializers.IntegerField()
    unread_count = serializers.IntegerField()

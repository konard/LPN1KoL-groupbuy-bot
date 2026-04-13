"""
Chat models for GroupBuy Bot
Supports real-time messaging in procurement chats
"""
from django.db import models
from users.models import User
from procurements.models import Procurement


class Message(models.Model):
    """Chat message in a procurement"""

    class MessageType(models.TextChoices):
        TEXT = 'text', 'Text'
        IMAGE = 'image', 'Image'
        FILE = 'file', 'File'
        SYSTEM = 'system', 'System'

    procurement = models.ForeignKey(
        Procurement, on_delete=models.CASCADE,
        related_name='messages'
    )
    user = models.ForeignKey(
        User, on_delete=models.SET_NULL,
        null=True, related_name='messages'
    )
    message_type = models.CharField(
        max_length=20, choices=MessageType.choices,
        default=MessageType.TEXT
    )
    text = models.TextField()
    attachment_url = models.URLField(blank=True)
    is_edited = models.BooleanField(default=False)
    is_deleted = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'chat_messages'
        indexes = [
            models.Index(fields=['procurement', 'created_at'], name='chat_messa_procure_a1b2c3_idx'),
            models.Index(fields=['user'], name='chat_messa_user_id_d4e5f6_idx'),
        ]
        ordering = ['created_at']

    def __str__(self):
        return f"Message by {self.user} in {self.procurement.title}"


class MessageRead(models.Model):
    """Track read status of messages"""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='read_messages')
    procurement = models.ForeignKey(Procurement, on_delete=models.CASCADE, related_name='read_status')
    last_read_message = models.ForeignKey(
        Message, on_delete=models.SET_NULL,
        null=True, related_name='read_by'
    )
    last_read_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'message_reads'
        unique_together = ['user', 'procurement']

    def __str__(self):
        return f"{self.user} in {self.procurement.title}"


class Notification(models.Model):
    """User notifications"""

    class NotificationType(models.TextChoices):
        NEW_MESSAGE = 'new_message', 'New Message'
        PROCUREMENT_UPDATE = 'procurement_update', 'Procurement Update'
        PAYMENT_REQUIRED = 'payment_required', 'Payment Required'
        PAYMENT_RECEIVED = 'payment_received', 'Payment Received'
        PROCUREMENT_COMPLETED = 'procurement_completed', 'Procurement Completed'
        SYSTEM = 'system', 'System'
        ADMIN_MESSAGE = 'admin_message', 'Admin Message'

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='notifications')
    notification_type = models.CharField(max_length=30, choices=NotificationType.choices)
    title = models.CharField(max_length=200)
    message = models.TextField()
    procurement = models.ForeignKey(
        Procurement, on_delete=models.CASCADE,
        null=True, blank=True, related_name='notifications'
    )
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'notifications'
        indexes = [
            models.Index(fields=['user', 'is_read'], name='notificati_user_id_g7h8i9_idx'),
            models.Index(fields=['created_at'], name='notificati_created_j0k1l2_idx'),
        ]
        ordering = ['-created_at']

    def __str__(self):
        return f"Notification for {self.user}: {self.title}"

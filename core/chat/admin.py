from django.contrib import admin
from .models import Message, MessageRead, Notification


@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    list_display = ['id', 'user', 'procurement', 'message_type', 'text_preview', 'is_deleted', 'created_at']
    list_filter = ['message_type', 'is_deleted', 'created_at']
    search_fields = ['text', 'user__first_name', 'procurement__title']
    readonly_fields = ['created_at', 'updated_at']

    def text_preview(self, obj):
        return obj.text[:50] + '...' if len(obj.text) > 50 else obj.text
    text_preview.short_description = 'Text'


@admin.register(MessageRead)
class MessageReadAdmin(admin.ModelAdmin):
    list_display = ['id', 'user', 'procurement', 'last_read_at']
    search_fields = ['user__first_name', 'procurement__title']


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ['id', 'user', 'notification_type', 'title', 'is_read', 'created_at']
    list_filter = ['notification_type', 'is_read', 'created_at']
    search_fields = ['user__first_name', 'title', 'message']

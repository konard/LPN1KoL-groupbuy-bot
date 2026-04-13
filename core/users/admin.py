from django.contrib import admin
from .models import User, UserSession


@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    list_display = ['id', 'first_name', 'last_name', 'platform', 'role', 'balance', 'has_selfie', 'is_active', 'created_at']
    list_filter = ['platform', 'role', 'is_active', 'is_verified']
    search_fields = ['first_name', 'last_name', 'username', 'email', 'phone', 'platform_user_id']
    readonly_fields = ['created_at', 'updated_at', 'selfie_file_id']
    fieldsets = (
        (None, {
            'fields': ('platform', 'platform_user_id', 'username', 'first_name', 'last_name'),
        }),
        ('Contact', {
            'fields': ('phone', 'email'),
        }),
        ('Identity verification', {
            'fields': ('selfie_file_id',),
            'description': 'Selfie photo captured during registration (Telegram file_id). Visible to admins only.',
        }),
        ('Role & Balance', {
            'fields': ('role', 'balance'),
        }),
        ('Status', {
            'fields': ('is_active', 'is_verified', 'language_code'),
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
        }),
    )

    @admin.display(boolean=True, description='Selfie')
    def has_selfie(self, obj):
        return bool(obj.selfie_file_id)


@admin.register(UserSession)
class UserSessionAdmin(admin.ModelAdmin):
    list_display = ['id', 'user', 'dialog_type', 'dialog_state', 'created_at']
    list_filter = ['dialog_type']
    search_fields = ['user__first_name', 'user__platform_user_id']

from django.contrib import admin
from .models import Category, Procurement, Participant


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ['id', 'name', 'parent', 'is_active', 'created_at']
    list_filter = ['is_active', 'parent']
    search_fields = ['name', 'description']


@admin.register(Procurement)
class ProcurementAdmin(admin.ModelAdmin):
    list_display = ['id', 'title', 'organizer', 'category', 'status', 'target_amount', 'current_amount', 'deadline']
    list_filter = ['status', 'category', 'city', 'is_featured']
    search_fields = ['title', 'description', 'city']
    readonly_fields = ['current_amount', 'created_at', 'updated_at']
    date_hierarchy = 'created_at'


@admin.register(Participant)
class ParticipantAdmin(admin.ModelAdmin):
    list_display = ['id', 'user', 'procurement', 'quantity', 'amount', 'status', 'is_active']
    list_filter = ['status', 'is_active']
    search_fields = ['user__first_name', 'procurement__title']

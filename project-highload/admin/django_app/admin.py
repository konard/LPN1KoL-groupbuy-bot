from django.contrib import admin

from django_app.models import Item


@admin.register(Item)
class ItemAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "created_at")
    search_fields = ("name", "description")
    readonly_fields = ("id", "created_at")

"""
URL configuration for Chat API
"""
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import MessageViewSet, NotificationViewSet

router = DefaultRouter()
router.register(r'messages', MessageViewSet, basename='message')
router.register(r'notifications', NotificationViewSet, basename='notification')

urlpatterns = [
    path('', include(router.urls)),
]

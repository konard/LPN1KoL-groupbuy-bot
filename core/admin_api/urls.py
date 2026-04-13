"""
Admin API URL Configuration
"""
from django.urls import path, include
from rest_framework.routers import DefaultRouter

from .views import (
    AdminAuthView,
    DashboardView,
    AnalyticsView,
    AdminUserViewSet,
    AdminProcurementViewSet,
    AdminPaymentViewSet,
    AdminTransactionViewSet,
    AdminCategoryViewSet,
    AdminMessageViewSet,
    AdminNotificationViewSet,
    AdminChatMessageView,
)

router = DefaultRouter()
router.register(r'users', AdminUserViewSet, basename='admin-users')
router.register(r'procurements', AdminProcurementViewSet, basename='admin-procurements')
router.register(r'payments', AdminPaymentViewSet, basename='admin-payments')
router.register(r'transactions', AdminTransactionViewSet, basename='admin-transactions')
router.register(r'categories', AdminCategoryViewSet, basename='admin-categories')
router.register(r'messages', AdminMessageViewSet, basename='admin-messages')
router.register(r'notifications', AdminNotificationViewSet, basename='admin-notifications')

urlpatterns = [
    path('auth/', AdminAuthView.as_view(), name='admin-auth'),
    path('dashboard/', DashboardView.as_view(), name='admin-dashboard'),
    path('analytics/', AnalyticsView.as_view(), name='admin-analytics'),
    path('chat/admin_message/', AdminChatMessageView.as_view(), name='admin-chat-message'),
    path('', include(router.urls)),
]

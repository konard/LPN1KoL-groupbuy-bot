"""
URL configuration for Payments API
"""
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import PaymentViewSet, TransactionViewSet

router = DefaultRouter()
router.register(r'transactions', TransactionViewSet, basename='transaction')
router.register(r'', PaymentViewSet, basename='payment')

urlpatterns = [
    path('', include(router.urls)),
]

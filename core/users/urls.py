"""
URL configuration for Users API
"""
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import UserViewSet, UserSessionViewSet

router = DefaultRouter()
router.register(r'', UserViewSet, basename='user')
router.register(r'sessions', UserSessionViewSet, basename='session')

urlpatterns = [
    path('', include(router.urls)),
]

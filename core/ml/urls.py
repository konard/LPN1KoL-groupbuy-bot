"""
URL configuration for the ML Analytics app.
"""

from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import MLModelViewSet, ProcurementPredictionViewSet

router = DefaultRouter()
router.register(r"models", MLModelViewSet, basename="ml-model")
router.register(r"predictions", ProcurementPredictionViewSet, basename="ml-prediction")

urlpatterns = [
    path("", include(router.urls)),
]

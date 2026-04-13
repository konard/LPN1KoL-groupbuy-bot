"""
URL configuration for Procurements API
"""
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import CategoryViewSet, ProcurementViewSet, ParticipantViewSet

router = DefaultRouter()
router.register(r'categories', CategoryViewSet, basename='category')
router.register(r'participants', ParticipantViewSet, basename='participant')
router.register(r'', ProcurementViewSet, basename='procurement')

# Instantiate ProcurementViewSet for explicit URL wiring.
# When ProcurementViewSet is registered at the empty prefix (r''), DRF
# normally generates ^user/(?P<user_id>[^/.]+)/$ correctly.  The explicit path
# below is an extra safety net that guarantees the endpoint is reachable even
# if a future DRF version changes empty-prefix action ordering.
_procurement_view = ProcurementViewSet.as_view({'get': 'user_procurements'})

urlpatterns = [
    # Explicit path must come BEFORE the router include so Django matches it
    # before the catch-all ^(?P<pk>[^/.]+)/$ detail route.
    path('user/<str:user_id>/', _procurement_view, name='procurement-user'),
    path('', include(router.urls)),
]

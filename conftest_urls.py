"""
Minimal URL configuration used only during pytest runs.
"""
from django.urls import path, include

urlpatterns = [
    path('api/users/', include('users.urls')),
    path('api/procurements/', include('procurements.urls')),
    path('api/chat/', include('chat.urls')),
    path('api/payments/', include('payments.urls')),
    path('api/admin/', include('admin_api.urls')),
    path('api/ml/', include('ml.urls')),
]

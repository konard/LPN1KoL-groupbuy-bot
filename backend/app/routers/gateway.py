"""
Роутер шлюза (/api/gateway/*).
В монолите gateway выполняет роль rate-limiting и health-агрегатора.
Логика проксирования сервисов не нужна — всё живёт в одном процессе.
"""
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Request

from app.dependencies import get_current_user

router = APIRouter(prefix="/api/gateway", tags=["gateway"])


@router.get("/status")
def gateway_status(request: Request):
    """Возвращает статус шлюза и список зарегистрированных маршрутов."""
    routes = [
        {"prefix": "/api/auth", "service": "auth-service"},
        {"prefix": "/api/purchases", "service": "purchase-service"},
        {"prefix": "/api/payments", "service": "payment-service"},
        {"prefix": "/api/chat", "service": "chat-service"},
        {"prefix": "/api/notifications", "service": "notification-service"},
        {"prefix": "/api/analytics", "service": "analytics-service"},
        {"prefix": "/api/search", "service": "search-service"},
        {"prefix": "/api/reputation", "service": "reputation-service"},
    ]
    return {
        "status": "ok",
        "mode": "monolith",
        "routes": routes,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@router.get("/me")
def gateway_me(user=Depends(get_current_user)):
    """Возвращает идентификатор и роль текущего пользователя (для отладки шлюза)."""
    return {
        "userId": user.id,
        "username": user.username,
        "role": "admin" if user.is_admin else "user",
    }

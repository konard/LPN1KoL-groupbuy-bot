"""
Pydantic-схемы для модуля уведомлений.
"""
from typing import Optional

from pydantic import BaseModel


class NotifyRequest(BaseModel):
    """Внутренний запрос на отправку уведомления."""
    user_id: int
    # Тип: email | telegram | push | in_app
    type: str
    subject: Optional[str] = None
    message: str
    # Дополнительные данные (email, telegram_id и т.д.)
    extra: Optional[dict] = None

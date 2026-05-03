"""
Pydantic-схемы для аналитического модуля.
"""
from typing import Any, Dict, Optional

from pydantic import BaseModel


class AnalyticsEvent(BaseModel):
    """Аналитическое событие, получаемое из Kafka или напрямую."""
    topic: str
    payload: Dict[str, Any]


class ReportGenerateRequest(BaseModel):
    """Запрос генерации отчёта и загрузки в S3/MinIO."""
    # Тип отчёта: purchases | payments | votes
    report_type: str
    description: Optional[str] = None

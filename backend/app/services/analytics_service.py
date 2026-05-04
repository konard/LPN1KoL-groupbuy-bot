"""
Бизнес-логика аналитики: in-memory хранилище событий, генерация отчётов, S3-загрузка.
"""
import io
import logging
from datetime import datetime, timezone
from typing import Any, Dict

logger = logging.getLogger(__name__)

# In-memory хранилище агрегированных статистик (в продакшне — ClickHouse)
_stats: Dict[str, Any] = {
    "purchase": {},
    "payment": {},
    "reputation": {},
    "search": {},
    "event_count": 0,
}

# Порог автоматической генерации отчёта
REPORT_THRESHOLD = 100


def record_event(topic: str, payload: Dict[str, Any]) -> None:
    """Записывает событие в in-memory хранилище."""
    _stats["event_count"] += 1

    if topic.startswith("purchase"):
        pid = payload.get("purchaseId", "unknown")
        _stats["purchase"].setdefault(pid, {"votes": 0, "winner": None})
        if "vote" in topic:
            _stats["purchase"][pid]["votes"] += 1
        elif "closed" in topic:
            _stats["purchase"][pid]["winner"] = payload.get("winnerId")

    elif topic.startswith("payment"):
        uid = payload.get("userId", "unknown")
        _stats["payment"].setdefault(uid, {"topups": 0, "holds": 0})
        if "topup" in topic:
            _stats["payment"][uid]["topups"] += float(payload.get("amount", 0))
        elif "hold" in topic:
            _stats["payment"][uid]["holds"] += float(payload.get("amount", 0))

    elif topic.startswith("review") or topic.startswith("complaint"):
        uid = payload.get("targetId", "unknown")
        _stats["reputation"].setdefault(uid, {"reviews": 0, "complaints": 0})
        if "review" in topic:
            _stats["reputation"][uid]["reviews"] += 1
        elif "complaint" in topic:
            _stats["reputation"][uid]["complaints"] += 1

    elif topic.startswith("search"):
        _stats["search"]["queries"] = _stats["search"].get("queries", 0) + 1


def get_stats(section: str) -> Dict[str, Any]:
    """Возвращает статистику по разделу."""
    if section == "summary":
        return {
            "event_count": _stats["event_count"],
            "purchase_count": len(_stats["purchase"]),
            "active_users": len(_stats["payment"]),
        }
    return _stats.get(section, {})


async def generate_report(report_type: str) -> bytes:
    """
    Генерирует отчёт в формате XLSX.
    Возвращает байты файла.
    """
    try:
        import openpyxl
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = report_type

        data = _stats.get(report_type, {})
        if not data:
            ws.append(["Нет данных"])
        else:
            first = next(iter(data.values()), {})
            ws.append(["ID"] + list(first.keys()))
            for entity_id, values in data.items():
                ws.append([entity_id] + list(values.values()))

        buffer = io.BytesIO()
        wb.save(buffer)
        return buffer.getvalue()
    except ImportError:
        logger.warning("openpyxl не установлен, генерация XLSX недоступна")
        return b""


async def upload_to_s3(data: bytes, filename: str) -> str:
    """
    Загружает файл в S3/MinIO и возвращает URL.
    При недоступности S3 логирует предупреждение.
    """
    from app.config import S3_ACCESS_KEY, S3_BUCKET, S3_ENDPOINT_URL, S3_SECRET_KEY
    if not S3_ENDPOINT_URL:
        logger.debug("S3 не настроен, загрузка пропущена")
        return ""
    try:
        import boto3
        s3 = boto3.client(
            "s3",
            endpoint_url=S3_ENDPOINT_URL,
            aws_access_key_id=S3_ACCESS_KEY,
            aws_secret_access_key=S3_SECRET_KEY,
        )
        s3.put_object(Bucket=S3_BUCKET, Key=filename, Body=data)
        return f"{S3_ENDPOINT_URL}/{S3_BUCKET}/{filename}"
    except Exception as exc:
        logger.error("Ошибка загрузки в S3: %s", exc)
        return ""

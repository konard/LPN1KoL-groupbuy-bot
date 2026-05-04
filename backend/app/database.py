"""
Подключение к базе данных.
Реэкспортирует Base, engine, SessionLocal и get_db из app.core.database
для обратной совместимости и для новых модулей.
"""
from sqlalchemy import text
from sqlalchemy.orm import Session

# Используем единственный экземпляр Base/engine из core
from app.core.database import Base, engine, SessionLocal, get_db  # noqa: F401


def check_db_health(db: Session) -> bool:
    """Быстрая проверка доступности БД (используется в /health)."""
    try:
        db.execute(text("SELECT 1"))
        return True
    except Exception:
        return False

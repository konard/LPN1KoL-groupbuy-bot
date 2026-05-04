FROM python:3.11-slim

WORKDIR /app

# Устанавливаем системные зависимости (curl для healthcheck, gcc для некоторых пакетов)
RUN apt-get update && apt-get install -y --no-install-recommends \
        curl \
        gcc \
        libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Копируем и устанавливаем зависимости отдельным слоем (кэш Docker)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Копируем исходный код приложения
COPY . .

# Healthcheck через /health endpoint
HEALTHCHECK --interval=10s --timeout=5s --retries=5 --start-period=30s \
    CMD curl -f http://localhost:${PORT:-8000}/health || exit 1

# Запуск: uvicorn с настройкой порта из переменной окружения
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000} --log-level ${LOG_LEVEL:-info}"]

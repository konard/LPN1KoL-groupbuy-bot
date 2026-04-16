FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .
RUN chmod +x /app/entrypoint.sh

EXPOSE 8002
ENTRYPOINT ["/app/entrypoint.sh"]
CMD ["sh", "-c", "gunicorn django_app.asgi:application -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:8002 --workers ${GUNICORN_WORKERS:-2} --timeout 60 --graceful-timeout 20"]

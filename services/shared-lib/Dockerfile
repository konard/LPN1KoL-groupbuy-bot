FROM python:3.11-slim
WORKDIR /app
COPY pyproject.toml .
COPY groupbuy_shared ./groupbuy_shared
RUN pip install --no-cache-dir -e .

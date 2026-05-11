FROM python:3.11-slim

WORKDIR /app

# Install system dependencies. postgresql-client provides `psql`, which
# entrypoint.sh uses to create the django_admin_db database before migrations.
# Without it the container loops with "psql: not found" (see issue #256).
RUN apt-get update && apt-get install -y \
    gcc \
    libpq-dev \
    postgresql-client \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy project
COPY . .

# Create staticfiles directory
RUN mkdir -p staticfiles

# Copy and enable the startup entrypoint script
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

EXPOSE 8000

ENTRYPOINT ["/entrypoint.sh"]

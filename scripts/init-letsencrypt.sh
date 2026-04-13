#!/bin/bash
# init-letsencrypt.sh — первоначальное получение SSL-сертификата Let's Encrypt
#
# Использование:
#   1. Убедитесь что в .env заданы переменные DOMAIN и CERTBOT_EMAIL
#   2. Убедитесь что домен уже указывает на IP этого сервера (DNS A-запись)
#   3. Запустите: bash scripts/init-letsencrypt.sh
#   4. После успешного получения сертификата запустите:
#      docker compose -f docker-compose.prod.yml up -d

set -e

# --- Загрузка переменных из .env ---
if [ -f .env ]; then
  # shellcheck disable=SC2046
  export $(grep -v '^#' .env | xargs)
fi

DOMAIN="${DOMAIN:-}"
EMAIL="${CERTBOT_EMAIL:-}"

if [ -z "$DOMAIN" ]; then
  echo "Ошибка: переменная DOMAIN не задана в .env"
  echo "Добавьте строку: DOMAIN=your-domain.com"
  exit 1
fi

if [ -z "$EMAIL" ]; then
  echo "Ошибка: переменная CERTBOT_EMAIL не задана в .env"
  echo "Добавьте строку: CERTBOT_EMAIL=your@email.com"
  exit 1
fi

echo "==> Домен: $DOMAIN"
echo "==> Email: $EMAIL"
echo ""

# --- Создание необходимых директорий ---
mkdir -p infrastructure/nginx/ssl
mkdir -p /var/lib/docker/volumes/groupbuy_certbot_webroot/_data 2>/dev/null || true

# --- Запуск временного nginx только для HTTP (ACME challenge) ---
echo "==> Запуск временного Nginx для ACME-валидации..."
docker compose -f docker-compose.prod.yml up -d nginx 2>/dev/null || true

# Дать nginx время запуститься
sleep 5

# --- Получение сертификата через webroot ---
echo "==> Запрос сертификата у Let's Encrypt..."
docker run --rm \
  -v groupbuy_letsencrypt_data:/etc/letsencrypt \
  -v groupbuy_certbot_webroot:/var/www/certbot \
  certbot/certbot certonly \
    --webroot \
    --webroot-path=/var/www/certbot \
    --email "$EMAIL" \
    --agree-tos \
    --no-eff-email \
    -d "$DOMAIN"

# --- Копирование сертификатов для Nginx ---
echo "==> Копирование сертификатов..."
docker run --rm \
  -v groupbuy_letsencrypt_data:/etc/letsencrypt:ro \
  -v "$(pwd)/infrastructure/nginx/ssl:/output" \
  alpine sh -c "
    cp /etc/letsencrypt/live/${DOMAIN}/fullchain.pem /output/fullchain.pem &&
    cp /etc/letsencrypt/live/${DOMAIN}/privkey.pem   /output/privkey.pem  &&
    chmod 644 /output/fullchain.pem &&
    chmod 600 /output/privkey.pem
  "

echo ""
echo "==> Сертификат успешно получен!"
echo "==> Файлы сохранены в infrastructure/nginx/ssl/"
echo ""
echo "Теперь запустите все сервисы:"
echo "  docker compose -f docker-compose.prod.yml up -d"
echo ""
echo "Автоматическое продление сертификата будет выполняться контейнером certbot."
echo "Для обновления сертификатов в nginx после продления добавьте в cron:"
echo "  0 3 1 * * cd /opt/groupbuy && docker compose -f docker-compose.prod.yml exec -T certbot certbot renew --quiet && docker compose -f docker-compose.prod.yml restart nginx"

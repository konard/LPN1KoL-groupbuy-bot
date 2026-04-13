#!/bin/bash
# setup-prod.sh — проверка окружения и первый запуск на продакшен-сервере
#
# Решает проблему: "password authentication failed for user postgres"
# Причина: если Docker-том postgres_data уже существует (например, после
# предыдущего запуска с другим паролем), PostgreSQL игнорирует переменную
# POSTGRES_PASSWORD при старте и использует старый пароль из тома.
#
# Решает проблему: "failed to bind host port for 0.0.0.0:80 ... address already in use"
# Причина: порты 80 или 443 уже заняты другим процессом (nginx, Apache и т.д.).
# Скрипт определяет занятый процесс и предлагает его остановить.
#
# Решает проблему: "container groupbuy-core is unhealthy"
# Причина: Rust-сервис должен установить соединение с PostgreSQL (до 10 попыток ×
# 3 с = 30 с) и выполнить миграции до того, как HTTP-сервер ответит на
# health-check. Это учтено в start_period healthcheck'а сервиса core.
#
# Использование:
#   bash scripts/setup-prod.sh               # интерактивный режим
#   bash scripts/setup-prod.sh --reset-db    # сбросить том postgres и запустить заново
#   bash scripts/setup-prod.sh --unified     # запустить объединённый стек (prod + микросервисы)
#
# Альтернативный вариант установки через snap (Ubuntu/Debian):
#   sudo snap install groupbuy-bot
#   sudo groupbuy-bot.setup

set -e

COMPOSE_FILE="docker-compose.prod.yml"
RESET_DB=false
UNIFIED=false

# --- Разбор аргументов ---
for arg in "$@"; do
  case "$arg" in
    --reset-db) RESET_DB=true ;;
    --unified)  UNIFIED=true  ;;
    --help|-h)
      echo "Использование: bash scripts/setup-prod.sh [--reset-db] [--unified]"
      echo ""
      echo "  --reset-db  Удалить существующий том PostgreSQL и начать с чистого листа."
      echo "              ВНИМАНИЕ: все данные БД будут потеряны!"
      echo "  --unified   Запустить объединённый стек: основное приложение + микросервисы"
      echo "              (docker-compose.unified.yml)."
      exit 0
      ;;
  esac
done

if [ "$UNIFIED" = true ]; then
  COMPOSE_FILE="docker-compose.unified.yml"
fi

# Determine the Docker Compose project name (same logic Docker uses: basename of working dir,
# lowercased with non-alphanumeric chars replaced by hyphens — matching Docker Compose behaviour).
PROJECT_NAME=$(basename "$(pwd)" | tr '[:upper:]' '[:lower:]' | sed 's/[^a-z0-9]/-/g')
VOLUME_NAME="${PROJECT_NAME}_postgres_data"

echo "==> GroupBuy Bot — подготовка продакшен-окружения"
echo ""

# --- 1. Проверка наличия .env ---
if [ ! -f .env ]; then
  echo "ОШИБКА: файл .env не найден."
  echo "Скопируйте .env.example и заполните переменные:"
  echo "  cp .env.example .env && nano .env"
  exit 1
fi

# --- 2. Загрузка переменных из .env ---
# shellcheck disable=SC2046
export $(grep -v '^#' .env | grep -v '^$' | xargs)

# --- 3. Проверка обязательных переменных ---
MISSING_VARS=()
[ -z "${DB_NAME:-}" ]     && MISSING_VARS+=("DB_NAME")
[ -z "${DB_USER:-}" ]     && MISSING_VARS+=("DB_USER")
[ -z "${DB_PASSWORD:-}" ] && MISSING_VARS+=("DB_PASSWORD")
[ -z "${TELEGRAM_TOKEN:-}" ] && MISSING_VARS+=("TELEGRAM_TOKEN")
[ -z "${JWT_SECRET:-}" ]  && MISSING_VARS+=("JWT_SECRET")
[ -z "${DOMAIN:-}" ]      && MISSING_VARS+=("DOMAIN")
[ -z "${CERTBOT_EMAIL:-}" ] && MISSING_VARS+=("CERTBOT_EMAIL")

if [ ${#MISSING_VARS[@]} -gt 0 ]; then
  echo "ОШИБКА: в .env не заданы следующие обязательные переменные:"
  for v in "${MISSING_VARS[@]}"; do
    echo "  - $v"
  done
  echo ""
  echo "Откройте .env и заполните все переменные: nano .env"
  exit 1
fi

echo "  [OK] .env найден, обязательные переменные заданы"

# --- 4. Проверка установки Docker ---
if ! command -v docker &>/dev/null; then
  echo ""
  echo "ОШИБКА: Docker не установлен."
  echo "Установите Docker:"
  echo "  curl -fsSL https://get.docker.com | sh"
  echo "  sudo usermod -aG docker \$USER && newgrp docker"
  exit 1
fi

if ! docker compose version &>/dev/null; then
  echo ""
  echo "ОШИБКА: Docker Compose (плагин) не найден."
  echo "Убедитесь, что установлен Docker Engine >= 24 или выполните:"
  echo "  sudo apt-get install docker-compose-plugin"
  exit 1
fi

echo "  [OK] Docker и Docker Compose доступны"

# --- 5. Проверка занятости портов 80, 443 и 8002 ---
# Симптом: "failed to bind host port for 0.0.0.0:80 ... address already in use"
# Причина: другой процесс (nginx, Apache, Caddy и т.д.) уже слушает этот порт.
# Для освобождения портов используется скрипт free-ports.sh.
bash scripts/free-ports.sh || true

# --- 6. Обнаружение устаревшего тома PostgreSQL ---
# Симптом: том существует, но пароль в .env отличается от того,
# с которым был инициализирован том — PostgreSQL откажет в подключении.
# ПРИЧИНА ошибки "password authentication failed for user postgres":
#   PostgreSQL применяет POSTGRES_PASSWORD только при первой инициализации тома.
#   Если том уже существует (например, после предыдущего запуска с другим
#   паролем), переменная окружения ИГНОРИРУЕТСЯ и используется старый пароль.

VOLUME_EXISTS=false
if docker volume inspect "$VOLUME_NAME" &>/dev/null; then
  VOLUME_EXISTS=true
fi

if [ "$VOLUME_EXISTS" = true ] && [ "$RESET_DB" = false ]; then
  echo ""
  echo "  [!] Том PostgreSQL '$VOLUME_NAME' уже существует."
  echo "      ВАЖНО: PostgreSQL устанавливает пароль ТОЛЬКО при первом запуске."
  echo "      Если пароль DB_PASSWORD в .env был изменён с момента создания тома,"
  echo "      контейнер core завершится с ошибкой:"
  echo "        'password authentication failed for user \"postgres\"'"
  echo "      Для исправления выберите вариант 2 (сброс тома)."
  echo ""
  echo "  Выберите действие:"
  echo "    1) Продолжить (том не трогать — данные сохранятся, пароль не изменится)"
  echo "    2) Сбросить том (УДАЛИТЬ все данные БД и начать заново с текущим паролем)"
  echo "    q) Отмена"
  echo ""
  read -r -p "  Ваш выбор [1/2/q]: " choice
  case "$choice" in
    2)
      RESET_DB=true
      ;;
    q|Q)
      echo "Отменено."
      exit 0
      ;;
    *)
      echo "  Продолжаем без изменений тома."
      ;;
  esac
fi

if [ "$RESET_DB" = true ]; then
  echo ""
  echo "  [!] Остановка контейнеров и удаление тома '$VOLUME_NAME'..."
  docker compose -f "$COMPOSE_FILE" down 2>/dev/null || true
  docker volume rm "$VOLUME_NAME" 2>/dev/null || true
  echo "  [OK] Том удалён. PostgreSQL будет инициализирован заново."
fi

# --- 7. Создание директорий для nginx ---
mkdir -p infrastructure/nginx/ssl

# --- 8. Получение SSL-сертификата (если ещё нет) ---
CERT_PATH="infrastructure/nginx/ssl/fullchain.pem"
if [ ! -f "$CERT_PATH" ]; then
  echo ""
  echo "  SSL-сертификат не найден. Запуск init-letsencrypt.sh..."
  bash scripts/init-letsencrypt.sh
else
  echo "  [OK] SSL-сертификат уже существует"
fi

# --- 9. Запуск всех сервисов ---
echo ""
echo "==> Запуск сервисов..."
docker compose -f "$COMPOSE_FILE" up -d

echo ""
echo "==> Проверка состояния контейнеров..."
sleep 5
docker compose -f "$COMPOSE_FILE" ps

echo ""
echo "==> Проверка подключения к API..."
RETRIES=10
for i in $(seq 1 $RETRIES); do
  if curl -sf http://localhost:8000/health > /dev/null 2>&1; then
    echo "  [OK] API доступен: http://localhost:8000/health"
    break
  fi
  if [ "$i" -eq "$RETRIES" ]; then
    echo "  [!] API недоступен после $RETRIES попыток. Проверьте логи:"
    echo "      docker compose -f $COMPOSE_FILE logs core"
  else
    echo "  ... ожидание API (попытка $i/$RETRIES)..."
    sleep 6
  fi
done

echo ""
echo "==> Готово!"
echo "    API:      https://${DOMAIN}/api/"
echo "    Фронтенд: https://${DOMAIN}/"
echo ""
echo "    Логи:     docker compose -f $COMPOSE_FILE logs -f"
echo "    Статус:   docker compose -f $COMPOSE_FILE ps"
echo ""
echo "    Создать суперпользователя для Django-админки:"
echo "      bash scripts/create-superuser.sh"

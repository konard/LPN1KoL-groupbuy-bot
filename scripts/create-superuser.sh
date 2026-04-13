#!/bin/bash
# create-superuser.sh — создание суперпользователя для Django-админки GroupBuy Bot
#
# Решает задачу: добавить суперпользователя в админ-панель на продакшен-сервере.
# Суперпользователь может входить по адресу /admin/ и иметь доступ ко всем
# разделам Django-административной панели.
#
# Использование (интерактивный режим):
#   bash scripts/create-superuser.sh
#
# Использование (неинтерактивный режим — для CI/CD или скриптов):
#   DJANGO_SUPERUSER_USERNAME=admin \
#   DJANGO_SUPERUSER_PASSWORD=secret \
#   DJANGO_SUPERUSER_EMAIL=admin@example.com \
#   bash scripts/create-superuser.sh --non-interactive
#
# Дополнительные параметры:
#   --compose-file FILE   Путь к docker-compose файлу (по умолчанию: docker-compose.prod.yml)
#   --help                Показать эту справку

set -e

COMPOSE_FILE="docker-compose.prod.yml"
NON_INTERACTIVE=false
CONTAINER="django-admin"

# --- Разбор аргументов ---
while [[ $# -gt 0 ]]; do
  case "$1" in
    --non-interactive)
      NON_INTERACTIVE=true
      shift
      ;;
    --compose-file)
      COMPOSE_FILE="$2"
      shift 2
      ;;
    --help|-h)
      echo "Использование: bash scripts/create-superuser.sh [параметры]"
      echo ""
      echo "  Создаёт суперпользователя Django для входа в административную панель."
      echo ""
      echo "Параметры:"
      echo "  --non-interactive          Неинтерактивный режим: данные берутся из переменных окружения."
      echo "  --compose-file FILE        Путь к файлу docker-compose (по умолчанию: docker-compose.prod.yml)."
      echo "  --help, -h                 Показать эту справку."
      echo ""
      echo "Переменные окружения для неинтерактивного режима:"
      echo "  DJANGO_SUPERUSER_USERNAME  Имя пользователя (обязательно)"
      echo "  DJANGO_SUPERUSER_PASSWORD  Пароль (обязательно)"
      echo "  DJANGO_SUPERUSER_EMAIL     Email (необязательно, по умолчанию пустой)"
      echo ""
      echo "Примеры:"
      echo "  # Интерактивный режим (запрашивает username, email, password):"
      echo "  bash scripts/create-superuser.sh"
      echo ""
      echo "  # Неинтерактивный режим:"
      echo "  DJANGO_SUPERUSER_USERNAME=admin \\"
      echo "  DJANGO_SUPERUSER_PASSWORD=secret123 \\"
      echo "  DJANGO_SUPERUSER_EMAIL=admin@example.com \\"
      echo "  bash scripts/create-superuser.sh --non-interactive"
      exit 0
      ;;
    *)
      echo "Неизвестный параметр: $1"
      echo "Используйте --help для справки."
      exit 1
      ;;
  esac
done

echo "==> GroupBuy Bot — создание суперпользователя Django"
echo ""

# --- 1. Проверка docker compose ---
if ! docker compose version &>/dev/null; then
  echo "ОШИБКА: Docker Compose (плагин) не найден."
  echo "Убедитесь, что установлен Docker Engine >= 24 или выполните:"
  echo "  sudo apt-get install docker-compose-plugin"
  exit 1
fi

# --- 2. Проверка наличия compose-файла ---
if [ ! -f "$COMPOSE_FILE" ]; then
  echo "ОШИБКА: файл '$COMPOSE_FILE' не найден."
  echo "Запустите скрипт из корневой директории проекта или укажите путь:"
  echo "  bash scripts/create-superuser.sh --compose-file путь/к/docker-compose.yml"
  exit 1
fi

# --- 3. Проверка, что контейнер запущен ---
if ! docker compose -f "$COMPOSE_FILE" ps --status running "$CONTAINER" 2>/dev/null | grep -q "$CONTAINER"; then
  echo "ОШИБКА: контейнер '$CONTAINER' не запущен."
  echo "Сначала запустите сервисы:"
  echo "  docker compose -f $COMPOSE_FILE up -d"
  exit 1
fi

echo "  [OK] Контейнер '$CONTAINER' запущен"
echo ""

# --- 4. Создание суперпользователя ---
if [ "$NON_INTERACTIVE" = true ]; then
  # Неинтерактивный режим: используем переменные окружения
  if [ -z "${DJANGO_SUPERUSER_USERNAME:-}" ]; then
    echo "ОШИБКА: переменная DJANGO_SUPERUSER_USERNAME не задана."
    echo "Задайте переменные окружения или используйте интерактивный режим."
    exit 1
  fi

  if [ -z "${DJANGO_SUPERUSER_PASSWORD:-}" ]; then
    echo "ОШИБКА: переменная DJANGO_SUPERUSER_PASSWORD не задана."
    echo "Задайте переменные окружения или используйте интерактивный режим."
    exit 1
  fi

  DJANGO_SUPERUSER_EMAIL="${DJANGO_SUPERUSER_EMAIL:-}"

  echo "  Создание суперпользователя '${DJANGO_SUPERUSER_USERNAME}'..."
  docker compose -f "$COMPOSE_FILE" exec \
    -e DJANGO_SUPERUSER_USERNAME="${DJANGO_SUPERUSER_USERNAME}" \
    -e DJANGO_SUPERUSER_PASSWORD="${DJANGO_SUPERUSER_PASSWORD}" \
    -e DJANGO_SUPERUSER_EMAIL="${DJANGO_SUPERUSER_EMAIL}" \
    "$CONTAINER" \
    python manage.py createsuperuser --no-input
else
  # Интерактивный режим: Django запросит username, email, password
  echo "  Запуск интерактивного создания суперпользователя..."
  echo "  (Введите имя пользователя, email и пароль по запросу)"
  echo ""
  docker compose -f "$COMPOSE_FILE" exec -it "$CONTAINER" \
    python manage.py createsuperuser
fi

echo ""
echo "==> Суперпользователь успешно создан!"
echo ""
echo "    Войдите в административную панель по адресу:"
echo "    https://\${DOMAIN}/api/admin/"
echo ""
echo "    Если переменная DOMAIN не задана, используйте адрес сервера."

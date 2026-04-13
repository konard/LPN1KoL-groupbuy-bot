#!/bin/bash
# setup-domain.sh — привязка домена к VDS-серверу
#
# Назначение:
#   Помогает привязать домен к VDS-серверу на billing.ihor-hosting.ru:
#   — показывает IP-адрес текущего сервера
#   — выводит пошаговую инструкцию по настройке DNS
#   — ждёт распространения DNS и проверяет что домен указывает на этот сервер
#   — после подтверждения DNS запускает получение SSL-сертификата
#
# Использование:
#   bash scripts/setup-domain.sh
#   bash scripts/setup-domain.sh --domain example.com --email admin@example.com
#   bash scripts/setup-domain.sh --check-only   # только проверить DNS, не получать сертификат

set -e

# --- Аргументы командной строки ---
DOMAIN=""
EMAIL=""
CHECK_ONLY=false

while [[ $# -gt 0 ]]; do
  case "$1" in
    --domain)   DOMAIN="$2"; shift 2 ;;
    --email)    EMAIL="$2";  shift 2 ;;
    --check-only) CHECK_ONLY=true; shift ;;
    --help|-h)
      echo "Использование: bash scripts/setup-domain.sh [ОПЦИИ]"
      echo ""
      echo "  --domain <домен>    Доменное имя (например: example.com)"
      echo "  --email  <email>    Email для уведомлений Let's Encrypt"
      echo "  --check-only        Только проверить DNS, не получать сертификат"
      echo ""
      echo "Если --domain и --email не указаны, они будут прочитаны из .env"
      exit 0
      ;;
    *)
      echo "Неизвестный аргумент: $1. Запустите с --help для справки."
      exit 1
      ;;
  esac
done

# --- Цвета для вывода ---
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

info()    { echo -e "${BLUE}  [i]${NC} $*"; }
ok()      { echo -e "${GREEN}  [OK]${NC} $*"; }
warn()    { echo -e "${YELLOW}  [!]${NC} $*"; }
error()   { echo -e "${RED}  [ERR]${NC} $*"; }

echo ""
echo "================================================"
echo "  GroupBuy Bot — Привязка домена к VDS-серверу"
echo "================================================"
echo ""

# --- Загрузка .env если есть ---
if [ -f .env ]; then
  # shellcheck disable=SC2046
  export $(grep -v '^#' .env | grep -v '^$' | xargs) 2>/dev/null || true
fi

# Приоритет: аргументы командной строки > .env
[ -z "$DOMAIN" ] && DOMAIN="${DOMAIN:-}"
[ -z "$EMAIL"  ] && EMAIL="${CERTBOT_EMAIL:-}"

# Если всё ещё пусто — спросить у пользователя
if [ -z "$DOMAIN" ]; then
  echo -n "  Введите доменное имя (например, example.com): "
  read -r DOMAIN
fi

if [ -z "$EMAIL" ] && [ "$CHECK_ONLY" = false ]; then
  echo -n "  Введите email для Let's Encrypt (например, admin@example.com): "
  read -r EMAIL
fi

if [ -z "$DOMAIN" ]; then
  error "Доменное имя не задано. Укажите --domain или добавьте DOMAIN= в .env"
  exit 1
fi

# --- Шаг 1: Определение IP-адреса сервера ---
echo ""
echo "Шаг 1. Определение IP-адреса этого сервера..."
echo ""

SERVER_IP=""
# Пробуем несколько источников для надёжности
for url in "https://api.ipify.org" "https://ifconfig.me/ip" "https://icanhazip.com"; do
  SERVER_IP=$(curl -sf --max-time 5 "$url" 2>/dev/null | tr -d '[:space:]') || true
  if [[ "$SERVER_IP" =~ ^[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
    break
  fi
  SERVER_IP=""
done

# Резервный вариант через hostname
if [ -z "$SERVER_IP" ]; then
  SERVER_IP=$(hostname -I 2>/dev/null | awk '{print $1}') || true
fi

if [ -z "$SERVER_IP" ]; then
  warn "Не удалось автоматически определить IP-адрес сервера."
  echo -n "  Введите IP-адрес сервера вручную: "
  read -r SERVER_IP
fi

ok "IP-адрес этого сервера: ${YELLOW}${SERVER_IP}${NC}"

# --- Шаг 2: Инструкция по настройке DNS ---
echo ""
echo "================================================================"
echo " Шаг 2. Настройте DNS-записи в панели управления хостингом"
echo "================================================================"
echo ""
echo "  Панель управления: https://billing.ihor-hosting.ru/"
echo ""
echo "  Инструкция:"
echo "  1. Войдите в https://billing.ihor-hosting.ru/"
echo "  2. Перейдите в раздел «Мои услуги» → выберите VDS-сервер"
echo "     (IP сервера должен совпадать с указанным выше)"
echo "  3. Если домен зарегистрирован здесь:"
echo "       «Домены» → выберите домен → «DNS-управление»"
echo "     Если домен у другого регистратора:"
echo "       Откройте DNS-настройки у вашего регистратора"
echo ""
echo "  4. Создайте (или обновите) следующие DNS-записи:"
echo ""
echo "  ┌──────┬──────────────────┬──────────────────────┬─────┐"
echo "  │ Тип  │ Имя (Host)       │ Значение (Value)     │ TTL │"
echo "  ├──────┼──────────────────┼──────────────────────┼─────┤"
printf "  │ A    │ %-16s │ %-20s │ 300 │\n" "@" "$SERVER_IP"
printf "  │ A    │ %-16s │ %-20s │ 300 │\n" "www" "$SERVER_IP"
echo "  └──────┴──────────────────┴──────────────────────┴─────┘"
echo ""
echo "     @ (или пусто) — корневой домен: ${DOMAIN}"
echo "     www           — поддомен: www.${DOMAIN}"
echo "     TTL 300       — время распространения: ~5 минут"
echo ""
warn "Если вы меняете NS-серверы, распространение может занять до 24 часов."

# --- Шаг 3: Ожидание и проверка DNS ---
echo ""
echo "================================================================"
echo " Шаг 3. Проверка распространения DNS"
echo "================================================================"
echo ""

# Функция проверки DNS
check_dns() {
  local domain="$1"
  local expected_ip="$2"
  local resolved_ip=""

  # Пробуем nslookup, dig или host — что доступно
  if command -v dig &>/dev/null; then
    resolved_ip=$(dig +short "$domain" A 2>/dev/null | grep -E '^[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+$' | head -1)
  elif command -v nslookup &>/dev/null; then
    resolved_ip=$(nslookup "$domain" 2>/dev/null | awk '/^Address: / { print $2 }' | tail -1)
  elif command -v host &>/dev/null; then
    resolved_ip=$(host "$domain" 2>/dev/null | awk '/has address/ { print $4 }' | head -1)
  else
    # Последний резерв — через curl к внешнему DNS API
    resolved_ip=$(curl -sf --max-time 5 "https://dns.google/resolve?name=${domain}&type=A" 2>/dev/null \
      | grep -o '"data":"[^"]*"' | head -1 | cut -d'"' -f4) || true
  fi

  echo "$resolved_ip"
}

MAX_WAIT_MINUTES=30
INTERVAL_SECONDS=30
MAX_ATTEMPTS=$(( MAX_WAIT_MINUTES * 60 / INTERVAL_SECONDS ))
ATTEMPT=0
DNS_OK=false

info "Домен для проверки: ${DOMAIN}"
info "Ожидаемый IP:       ${SERVER_IP}"
echo ""

while [ $ATTEMPT -lt $MAX_ATTEMPTS ]; do
  ATTEMPT=$(( ATTEMPT + 1 ))
  RESOLVED=$(check_dns "$DOMAIN" "$SERVER_IP")

  if [ "$RESOLVED" = "$SERVER_IP" ]; then
    ok "DNS обновился! ${DOMAIN} → ${SERVER_IP}"
    DNS_OK=true
    break
  else
    if [ -z "$RESOLVED" ]; then
      info "Попытка $ATTEMPT/$MAX_ATTEMPTS: DNS ещё не распространился (запись не найдена)..."
    else
      info "Попытка $ATTEMPT/$MAX_ATTEMPTS: ${DOMAIN} → ${RESOLVED} (ожидаем ${SERVER_IP})..."
    fi

    # Каждые 5 попыток напоминаем что нужно проверить DNS-настройки
    if (( ATTEMPT % 5 == 0 )); then
      warn "Ещё не обновился. Убедитесь что DNS-записи сохранены в панели хостинга."
    fi

    echo -n "  Следующая проверка через ${INTERVAL_SECONDS}с. Нажмите Enter чтобы проверить сейчас, или подождите: "
    # Ждём нажатия Enter или истечения таймера
    if read -r -t $INTERVAL_SECONDS; then
      : # Пользователь нажал Enter — проверяем немедленно
    fi
  fi
done

if [ "$DNS_OK" = false ]; then
  echo ""
  warn "DNS не распространился за ${MAX_WAIT_MINUTES} минут."
  warn "Это может занять до 24 часов при смене NS-серверов."
  echo ""
  echo -n "  Продолжить несмотря на то, что DNS ещё не обновился? [y/N]: "
  read -r FORCE
  if [[ "$FORCE" != "y" && "$FORCE" != "Y" ]]; then
    echo ""
    info "Запустите скрипт заново когда DNS обновится:"
    echo "    bash scripts/setup-domain.sh"
    echo ""
    info "Для ручной проверки DNS:"
    echo "    nslookup ${DOMAIN}"
    echo "    dig ${DOMAIN} A +short"
    exit 0
  fi
fi

# --- Завершение: только проверка DNS ---
if [ "$CHECK_ONLY" = true ]; then
  echo ""
  if [ "$DNS_OK" = true ]; then
    ok "DNS настроен корректно. Домен ${DOMAIN} указывает на ${SERVER_IP}."
    echo ""
    info "Для получения SSL-сертификата запустите:"
    echo "    bash scripts/init-letsencrypt.sh"
    echo "  или"
    echo "    bash scripts/setup-prod.sh"
  else
    warn "DNS пока не указывает на этот сервер."
  fi
  exit 0
fi

# --- Шаг 4: Получение SSL-сертификата ---
echo ""
echo "================================================================"
echo " Шаг 4. Получение SSL-сертификата (Let's Encrypt)"
echo "================================================================"
echo ""

if [ -z "$EMAIL" ]; then
  error "Email не задан. Укажите --email или добавьте CERTBOT_EMAIL= в .env"
  exit 1
fi

# Сохраняем DOMAIN и CERTBOT_EMAIL в .env если их там нет
if [ -f .env ]; then
  if ! grep -q "^DOMAIN=" .env; then
    echo "" >> .env
    echo "DOMAIN=${DOMAIN}" >> .env
    ok "Добавлено DOMAIN=${DOMAIN} в .env"
  fi
  if ! grep -q "^CERTBOT_EMAIL=" .env; then
    echo "CERTBOT_EMAIL=${EMAIL}" >> .env
    ok "Добавлено CERTBOT_EMAIL=${EMAIL} в .env"
  fi
fi

info "Запуск init-letsencrypt.sh для домена ${DOMAIN}..."
echo ""

DOMAIN="$DOMAIN" CERTBOT_EMAIL="$EMAIL" bash scripts/init-letsencrypt.sh

echo ""
echo "================================================================"
echo " Готово!"
echo "================================================================"
echo ""
ok "Домен ${DOMAIN} успешно привязан к серверу ${SERVER_IP}"
ok "SSL-сертификат получен и сохранён в infrastructure/nginx/ssl/"
echo ""
info "Следующий шаг — запустить все сервисы:"
echo "    bash scripts/setup-prod.sh"
echo ""
info "Или только Docker-контейнеры:"
echo "    docker compose -f docker-compose.prod.yml up -d"
echo ""
info "После запуска ваш сервис будет доступен по адресу:"
echo "    https://${DOMAIN}/"
echo ""

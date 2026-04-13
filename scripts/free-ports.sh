#!/bin/bash
# free-ports.sh — освобождение портов, используемых проектом GroupBuy Bot
#
# Решает проблему: "failed to bind host port ... address already in use"
# при запуске docker compose -f docker-compose.prod.yml up -d
#
# Определяет процессы, занимающие порты 80, 443 и 8002, и завершает их.
#
# Использование:
#   bash scripts/free-ports.sh            # интерактивный режим (по умолчанию)
#   bash scripts/free-ports.sh --force    # завершить процессы без подтверждения
#   bash scripts/free-ports.sh --help     # показать справку

set -e

FORCE=false

# --- Разбор аргументов ---
for arg in "$@"; do
  case "$arg" in
    --force|-f)
      FORCE=true
      ;;
    --help|-h)
      echo "Использование: bash scripts/free-ports.sh [--force]"
      echo ""
      echo "  Освобождает порты 80, 443 и 8002, используемые проектом GroupBuy Bot."
      echo "  Без флагов работает в интерактивном режиме — запрашивает подтверждение"
      echo "  перед остановкой каждого занятого процесса."
      echo ""
      echo "  --force, -f  Завершить занятые процессы без подтверждения."
      exit 0
      ;;
  esac
done

# Порты, используемые проектом в продакшен-конфигурации (docker-compose.prod.yml)
PORTS=(80 443 8002)

echo "==> GroupBuy Bot — освобождение портов"
echo ""

# Определяем PID процесса, занимающего указанный порт
get_pid() {
  local port="$1"
  local pid=""

  if command -v ss &>/dev/null; then
    pid=$(ss -tlnp "sport = :${port}" 2>/dev/null \
      | grep -oP '(?<=pid=)\d+' | head -1)
  elif command -v lsof &>/dev/null; then
    pid=$(lsof -ti ":${port}" -sTCP:LISTEN 2>/dev/null | head -1)
  elif command -v fuser &>/dev/null; then
    pid=$(fuser "${port}/tcp" 2>/dev/null | awk '{print $1}')
  fi

  echo "$pid"
}

# Определяем имя процесса по PID
get_name() {
  local pid="$1"
  local name=""

  if [ -f "/proc/${pid}/comm" ]; then
    name=$(cat "/proc/${pid}/comm" 2>/dev/null)
  else
    name=$(ps -p "$pid" -o comm= 2>/dev/null || echo "неизвестен")
  fi

  echo "$name"
}

# Завершает процесс, занимающий порт: сначала через systemctl, затем через kill
free_port() {
  local port="$1"
  local pid
  local service_name

  pid=$(get_pid "$port")

  if [ -z "$pid" ]; then
    echo "  [OK] Порт ${port} свободен"
    return 0
  fi

  service_name=$(get_name "$pid")

  echo "  [!] Порт ${port} занят процессом '${service_name}' (PID ${pid})"

  if [ "$FORCE" = false ]; then
    echo ""
    read -r -p "      Остановить '${service_name}'? [y/N]: " answer
    case "$answer" in
      y|Y|yes|YES) ;;
      *)
        echo "      Пропущено. Порт ${port} остался занят."
        return 0
        ;;
    esac
  fi

  echo "      Останавливаем '${service_name}'..."

  # Сначала пробуем systemctl (для systemd-сервисов: nginx, apache2, caddy и т.д.)
  if systemctl stop "${service_name}" 2>/dev/null; then
    echo "  [OK] Сервис '${service_name}' остановлен через systemctl."
    return 0
  fi

  # Резервный вариант: завершить процесс по PID
  if kill "$pid" 2>/dev/null; then
    sleep 1
    # Проверяем, что порт действительно освободился
    if [ -z "$(get_pid "$port")" ]; then
      echo "  [OK] Процесс PID ${pid} завершён, порт ${port} свободен."
    else
      echo "  [!] Процесс PID ${pid} завершён, но порт ${port} всё ещё занят."
      echo "      Попробуйте: sudo kill -9 ${pid}"
    fi
    return 0
  fi

  echo "  [!] Не удалось остановить процесс. Выполните вручную:"
  echo "      sudo systemctl stop ${service_name}"
  echo "      или"
  echo "      sudo kill ${pid}"
  return 1
}

ALL_FREE=true

for port in "${PORTS[@]}"; do
  if ! free_port "$port"; then
    ALL_FREE=false
  fi
done

echo ""
if [ "$ALL_FREE" = true ]; then
  echo "==> Готово! Все порты проверены."
else
  echo "==> Завершено с предупреждениями. Некоторые порты могут быть всё ещё заняты."
  echo "    Для принудительного завершения используйте:"
  echo "      sudo bash scripts/free-ports.sh --force"
  exit 1
fi

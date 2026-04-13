# Развёртывание GroupBuy на сервере с 1 ГБ RAM

Пошаговая инструкция для установки всех микросервисов на VPS/VDS с 1 ГБ оперативной памяти.

---

## 1. Требования к серверу

| Параметр | Минимум |
|----------|---------|
| **OS** | Ubuntu 22.04 LTS / Debian 12 |
| **CPU** | 1 vCPU (рекомендуется 2) |
| **RAM** | 1 ГБ |
| **Swap** | 2 ГБ (обязательно!) |
| **Диск** | 20 ГБ SSD |
| **Сеть** | Публичный IP, открытые порты 80, 443, 3000, 8000 |

> **Важно:** на 1 ГБ RAM обязательно нужен swap-файл минимум 2 ГБ. Без swap сборка Docker-образов и работа Kafka будут завершаться с ошибкой OOM.

---

## 2. Подготовка сервера

### 2.1. Подключение по SSH

```bash
ssh root@ВАШ_IP_АДРЕС
```

### 2.2. Обновление системы

```bash
apt update && apt upgrade -y
```

### 2.3. Создание swap-файла (2 ГБ)

```bash
fallocate -l 2G /swapfile
chmod 600 /swapfile
mkswap /swapfile
swapon /swapfile
echo '/swapfile none swap sw 0 0' >> /etc/fstab

# Оптимизация swap для сервера
sysctl vm.swappiness=10
echo 'vm.swappiness=10' >> /etc/sysctl.conf
```

### 2.4. Установка Docker и Docker Compose

```bash
# Установка Docker
curl -fsSL https://get.docker.com | sh

# Добавление текущего пользователя в группу docker (если не root)
usermod -aG docker $USER

# Проверка
docker --version
docker compose version
```

### 2.5. Установка Git

```bash
apt install -y git
```

---

## 3. Развёртывание проекта

### 3.1. Клонирование репозитория

```bash
cd /opt
git clone https://github.com/MixaByk1996/groupbuy-bot.git
cd groupbuy-bot
```

### 3.2. Настройка переменных окружения

```bash
cp .env.example .env
nano .env
```

Обязательно измените следующие значения в `.env`:

```env
# Безопасность — обязательно замените!
JWT_SECRET=ваш_длинный_случайный_ключ_минимум_32_символа
JWT_REFRESH_SECRET=другой_длинный_случайный_ключ
POSTGRES_PASSWORD=надёжный_пароль_для_бд
REDIS_PASSWORD=надёжный_пароль_для_redis

# Telegram бот (получить у @BotFather)
TELEGRAM_BOT_TOKEN=123456:ABC-DEF...

# SMTP для отправки писем (опционально)
# Яндекс: используйте пароль приложения (не пароль аккаунта).
# Адрес в SMTP_FROM должен совпадать с SMTP_USER — Яндекс отклоняет несовпадающих отправителей.
SMTP_HOST=smtp.yandex.ru
SMTP_PORT=587
SMTP_USER=your@yandex.ru
SMTP_PASS=пароль_приложения
SMTP_FROM=GroupBuy <your@yandex.ru>

# Платёжная система (опционально, для тестирования можно оставить пустым)
STRIPE_SECRET_KEY=
YOOKASSA_SHOP_ID=
YOOKASSA_SECRET_KEY=
```

Для генерации случайных ключей используйте:

```bash
openssl rand -hex 32
```

### 3.3. Запуск в лёгком режиме

```bash
# Сборка и запуск всех сервисов
docker compose -f docker-compose.light.yml up -d --build
```

> **Первая сборка** занимает 10–20 минут, так как Docker собирает образы для всех микросервисов. Последующие запуски — 1–2 минуты.

### 3.4. Проверка статуса

```bash
# Все контейнеры должны быть в статусе "Up" или "Up (healthy)"
docker compose -f docker-compose.light.yml ps

# Проверка логов при проблемах
docker compose -f docker-compose.light.yml logs --tail=50

# Проверка конкретного сервиса
docker compose -f docker-compose.light.yml logs gateway --tail=30
```

---

## 4. Проверка работоспособности

### 4.1. Проверка Gateway (главная точка входа)

```bash
curl http://localhost:3000/health
# Ожидаемый ответ: OK или {"status":"ok"}
```

### 4.2. Проверка Auth Service

```bash
curl http://localhost:3000/api/v1/auth/health
```

### 4.3. Проверка WebSocket (Centrifugo)

```bash
curl http://localhost:8000/health
```

### 4.4. Проверка всех сервисов разом

```bash
for port in 3000 4001 4002 4003 4004 4005 4006 4007 4008; do
  echo -n "Port $port: "
  curl -s -o /dev/null -w "%{http_code}" http://localhost:$port/health 2>/dev/null || echo "N/A"
  echo
done
```

---

## 5. Распределение памяти (лёгкий режим)

Конфигурация `docker-compose.light.yml` оптимизирована для 1 ГБ RAM:

| Сервис | Лимит RAM | Описание |
|--------|-----------|----------|
| PostgreSQL | 128 МБ | Единая БД для всех сервисов |
| Redis | 64 МБ | Кэш, сессии, rate limiting |
| Kafka | 192 МБ | Очередь событий |
| Zookeeper | 96 МБ | Координатор Kafka |
| Centrifugo | 32 МБ | WebSocket-сервер |
| Gateway (Go) | 32 МБ | API-шлюз |
| Auth (NestJS) | 64 МБ | Аутентификация |
| Purchase (NestJS) | 64 МБ | Закупки и голосования |
| Payment (Go) | 32 МБ | Платежи |
| Chat (Go) | 32 МБ | Чат |
| Notification (Node.js) | 48 МБ | Уведомления |
| Analytics (Python) | 48 МБ | Аналитика |
| Search (Go) | 32 МБ | Поиск |
| Reputation (NestJS) | 48 МБ | Репутация |
| **Итого** | **~912 МБ** | + swap при необходимости |

### Что отключено в лёгком режиме

- **Elasticsearch** — поиск работает через Redis (базовый режим)
- **ClickHouse** — история чата хранится в PostgreSQL
- **MinIO** — отчёты сохраняются локально
- **Kafka-UI** — веб-интерфейс Kafka
- **Prometheus + Grafana** — мониторинг

> Все эти компоненты можно подключить позже при переезде на более мощный сервер, переключившись на `docker-compose.microservices.yml`.

---

## 6. Управление сервисами

### Остановка

```bash
docker compose -f docker-compose.light.yml down
```

### Перезапуск

```bash
docker compose -f docker-compose.light.yml restart
```

### Обновление (после git pull)

```bash
cd /opt/groupbuy-bot
git pull origin main
docker compose -f docker-compose.light.yml up -d --build
```

### Просмотр логов в реальном времени

```bash
docker compose -f docker-compose.light.yml logs -f
```

### Резервное копирование БД

```bash
docker compose -f docker-compose.light.yml exec postgres \
  pg_dumpall -U groupbuy > backup_$(date +%Y%m%d_%H%M%S).sql
```

### Восстановление БД из бэкапа

```bash
docker compose -f docker-compose.light.yml exec -i postgres \
  psql -U groupbuy -d auth_db < backup_YYYYMMDD_HHMMSS.sql
```

---

## 7. Настройка домена и HTTPS (опционально)

Если у вас есть домен, можно настроить Nginx с SSL:

```bash
apt install -y nginx certbot python3-certbot-nginx

# Создать конфигурацию Nginx
cat > /etc/nginx/sites-available/groupbuy <<'EOF'
server {
    listen 80;
    server_name ваш-домен.ru;

    location / {
        proxy_pass http://127.0.0.1:3000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    location /ws {
        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
EOF

ln -s /etc/nginx/sites-available/groupbuy /etc/nginx/sites-enabled/
nginx -t && systemctl reload nginx

# Получить SSL-сертификат
certbot --nginx -d ваш-домен.ru
```

---

## 8. Устранение проблем

### Контейнер перезапускается (OOMKilled)

```bash
# Проверьте, какой контейнер использует слишком много памяти
docker stats --no-stream

# Убедитесь, что swap включён
free -h
# Если swap = 0, создайте его (см. раздел 2.3)
```

### Kafka не запускается

```bash
# Kafka требует времени на старт после Zookeeper
docker compose -f docker-compose.light.yml restart kafka

# Проверьте логи
docker compose -f docker-compose.light.yml logs kafka --tail=30
```

### БД не найдена (purchase_db, payment_db и т.д.)

```bash
# Если init-databases.sh не сработал, создайте БД вручную
docker compose -f docker-compose.light.yml exec postgres psql -U groupbuy -d auth_db -c "
  CREATE DATABASE IF NOT EXISTS purchase_db;
  CREATE DATABASE IF NOT EXISTS payment_db;
  CREATE DATABASE IF NOT EXISTS chat_db;
  CREATE DATABASE IF NOT EXISTS reputation_db;
"
```

### Порт уже занят

```bash
# Найти процесс на порту 3000
lsof -i :3000
# или
ss -tlnp | grep 3000

# Остановить процесс
kill -9 <PID>
```

---

## 9. Миграция на полную конфигурацию

Когда сервер будет обновлён (4+ ГБ RAM), переключитесь на полную конфигурацию:

```bash
# Остановить лёгкий режим
docker compose -f docker-compose.light.yml down

# Запустить полную конфигурацию
docker compose -f docker-compose.microservices.yml up -d --build
```

Полная конфигурация добавляет:
- Elasticsearch для полнотекстового поиска
- ClickHouse для аналитики и истории чатов
- MinIO для хранения файлов (прайс-листы, отчёты)
- Prometheus + Grafana для мониторинга
- Kafka-UI для управления очередями
- Отдельные PostgreSQL инстансы для каждого сервиса

---

## 10. Архитектура микросервисов

```
                  [Клиент / Telegram / WhatsApp]
                              |
                      [Gateway :3000]
                              |
          +-------------------+-------------------+
          |         |         |         |         |
    [Auth :4001] [Purchase  [Payment [Chat    [Notification
                  :4002]     :4003]   :4004]   :4005]
          |         |         |         |         |
          +---[PostgreSQL]----+    [Centrifugo :8000]
          |                   |
    [Search :4007]    [Analytics :4006]
          |                   |
    [Reputation :4008]   [Kafka]
          |
        [Redis]
```

Все сервисы общаются через:
- **REST API** — синхронные запросы через Gateway
- **Kafka** — асинхронные события (голосования, платежи, уведомления)
- **Centrifugo** — WebSocket в реальном времени (чат, обновления голосований)

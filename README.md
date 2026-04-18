# GroupBuy Bot v4.0

A scalable microservices platform for organizing group purchases, supporting 10M+ users across Telegram, WhatsApp, and WebSocket-based chat.

## Architecture (v4.0)

| Service | Technology | Purpose |
|---------|-----------|---------|
| Gateway | Go (gorilla/mux) | API routing, rate limiting, JWT, CORS |
| Auth | NestJS | JWT auth, 2FA (TOTP), registration |
| Purchase | NestJS + Kafka | Purchases, voting, commission, sagas |
| Payment | Go | Wallets, holds, escrow, commission |
| Chat | Go + Centrifugo | WebSocket chat, message history |
| Analytics | Python (FastAPI) | Reports, ML recommendations |
| Notification | Node.js | Push, email, Telegram/WhatsApp bots |
| Search | Go + Elasticsearch | Fuzzy search, saved filters |
| Reputation | NestJS | Reviews, ratings, arbitration |

Key features: organizer commission (0-10%), escrow for large purchases, 2FA, auto-rollback (Argo Rollouts), smart search with typo tolerance, reputation system with auto-blocking.

See [Deployment Guide](docs/DEPLOYMENT-v4.md) for full setup instructions.

---

## Описание функционала (на русском)

GroupBuy Bot — это многофункциональная платформа для организации совместных закупок (групповых покупок). Сервис позволяет пользователям объединяться для совместного приобретения товаров по оптовым ценам. Ниже приводится полное описание функционала платформы.

---

### Роли пользователей

В системе предусмотрены три роли:

- **Покупатель (Buyer)** — может просматривать активные закупки, вступать в них, оплачивать участие, общаться в чате закупки.
- **Организатор (Organizer)** — может создавать и управлять закупками, подтверждать участников, менять статусы закупки.
- **Поставщик (Supplier)** — может быть прикреплён к закупке для поставки товаров.

Каждый пользователь имеет профиль с:
- Именем, фамилией, именем пользователя
- Контактными данными (телефон, email)
- Личным балансом в рублях для оплаты
- Статусами верификации и активности
- Привязкой к платформе (Telegram, VK и др.)

---

### Закупки (совместные покупки)

#### Жизненный цикл закупки

Закупка проходит через следующие статусы:

1. **Черновик (DRAFT)** — создаётся организатором, ещё не активна.
2. **Активная (ACTIVE)** — открыта для вступления участников.
3. **Остановлена (STOPPED)** — набор участников прекращён (вручную или при достижении цели).
4. **Оплата (PAYMENT)** — участники производят оплату.
5. **Завершена (COMPLETED)** — закупка успешно завершена.
6. **Отменена (CANCELLED)** — закупка отменена.

#### Параметры закупки

При создании закупки организатор указывает:
- **Название и описание** товара
- **Категорию** (с иерархией и эмодзи-иконками)
- **Целевую сумму** для сбора
- **Цену за единицу** и **единицу измерения** (кг, штуки, литры и т.д.)
- **Дедлайн** — крайний срок сбора участников
- **Город и адрес доставки**
- **Лимит суммы** для автоматической остановки при достижении цели
- **Изображение** товара
- **Флаг "Рекомендуемая"** для продвижения закупки

#### Участие в закупке

Покупатель может:
- Просматривать список активных закупок с фильтрацией по статусу, категории и городу
- Просматривать детали закупки: прогресс сбора, количество участников, дней осталось
- Вступить в закупку, указав желаемое количество
- Покинуть закупку (отменить участие)
- Просматривать свои закупки (в которых участвует или которые организует)

Статусы участника: `PENDING` → `CONFIRMED` → `PAID` → `DELIVERED` (или `CANCELLED`)

---

### Платёжная система

Платформа поддерживает интеграцию с банковским сервисом для приёма платежей:

#### Точка Банк (Cyclops)
- Подписание API-запросов RSA-ключами
- Работа с номинальными счетами для безопасных транзакций
- Управление виртуальными счетами для каждого участника
- Подтверждение платежей через вебхуки

#### Типы операций
- **Пополнение баланса (DEPOSIT)** — пользователь пополняет личный баланс
- **Вывод средств (WITHDRAWAL)** — вывод средств с баланса
- **Оплата закупки (PROCUREMENT_PAYMENT)** — оплата участия в закупке

#### Статусы платежа
- `PENDING` — платёж создан, ожидает оплаты
- `WAITING_FOR_CAPTURE` — авторизация получена, ожидается подтверждение
- `SUCCEEDED` — платёж успешно завершён
- `CANCELLED` — платёж отменён
- `REFUNDED` — средства возвращены

#### История транзакций
Каждое изменение баланса фиксируется в журнале транзакций с типами:
- `DEPOSIT`, `WITHDRAWAL` — пополнение/вывод
- `PROCUREMENT_JOIN` — оплата вступления в закупку
- `PROCUREMENT_REFUND` — возврат за отменённую закупку
- `TRANSFER`, `BONUS` — переводы и бонусы

---

### Бот-команды (Telegram и VK)

Сервис доступен через мессенджеры. Все команды работают одинаково в Telegram и ВКонтакте:

#### Основные команды
| Команда | Описание |
|---------|----------|
| `/start` | Регистрация нового пользователя или приветствие вернувшегося |
| `/help` | Список доступных команд |
| `/profile` | Просмотр и редактирование профиля |
| `/balance` | Проверка баланса аккаунта |
| `/notifications` | Просмотр непрочитанных уведомлений |
| `/deposit` | Пополнение баланса |

#### Команды для закупок
| Команда | Описание |
|---------|----------|
| `/procurements` | Список активных закупок |
| `/my_procurements` | Мои закупки (организованные и участие) |
| `/search` | Поиск закупок по ключевым словам |
| `/create_procurement` | Создать новую закупку (только для организаторов) |

#### Команды для чата
| Команда | Описание |
|---------|----------|
| `/chat` | Открыть чат закупки (список доступных чатов) |

#### Команды для рассылок (для организаторов/администраторов)
| Команда | Описание |
|---------|----------|
| `/broadcast` | Отправка рекламных сообщений в Telegram-каналы |

Бот поддерживает интерактивные клавиатуры для навигации и многошаговые диалоги (FSM) для создания закупок и регистрации.

---

### Чат в реальном времени

Для каждой закупки предусмотрен чат:
- **Типы сообщений**: текст, изображение, файл, системное сообщение
- **Редактирование** и **мягкое удаление** сообщений
- **WebSocket** — мгновенная доставка новых сообщений всем участникам без перезагрузки страницы
- **Счётчик непрочитанных** сообщений для каждого чата
- **JWT-аутентификация** для безопасного подключения к WebSocket

---

### Уведомления

Пользователи получают уведомления о следующих событиях:
- **Новое сообщение в чате** закупки
- **Обновление статуса** закупки
- **Требуется оплата** по закупке
- **Платёж получен** успешно
- **Закупка завершена**
- **Системные уведомления**

---

### Веб-интерфейс (Frontend)

Платформа включает полноценный веб-интерфейс в стиле Telegram:
- **Личный кабинет** для каждой роли (покупатель, организатор, поставщик)
- **Просмотр закупок** со слайдером и фильтрами
- **Чат** с поддержкой WebSocket в реальном времени
- **Тёмная и светлая темы**
- **Адаптивный дизайн** для мобильных устройств

---

### Административная панель

Администраторы системы имеют доступ к полнофункциональной веб-панели управления (`/admin-panel/`):

#### Дашборд
- Статистика пользователей (всего, по ролям, по платформам, тренды регистрации)
- Статистика закупок (по статусам, количество активных, процент завершённых)
- Финансовая статистика (выручка, разбивка по статусам, временной анализ)
- Метрики активности (сообщения, уведомления)

#### Управление пользователями
- Просмотр всех пользователей с фильтрами
- Поиск по имени, email, телефону, ID платформы
- Переключение статусов активности и верификации
- Корректировка баланса с записью в журнал транзакций

#### Управление закупками
- Просмотр всех закупок с фильтрами по статусу, категории, городу
- Изменение статуса закупки
- Управление флагом "Рекомендуемая"
- Просмотр участников и их статусов

#### Мониторинг платежей
- Просмотр всех платежей с фильтрацией
- Статистика и сводка по платежам
- История транзакций

#### Управление категориями
- Создание, редактирование, удаление категорий
- Иерархическая структура (родительские и дочерние категории)
- Иконки категорий (эмодзи)

#### Управление сообщениями и уведомлениями
- Просмотр и модерация сообщений чата
- Массовая рассылка уведомлений всем пользователям
- Поиск по содержимому сообщений

---

### Искусственный интеллект (ML-аналитика)

Платформа поддерживает опциональную интеграцию с Plexe AI для аналитики закупок:

- **Предсказание успеха** — оценка вероятности достижения целевой суммы закупки
- **Прогнозирование спроса** — оценка потенциального спроса (в единицах) по категории и городу
- **Оптимизация цены** — рекомендация оптимальной цены за единицу для максимизации участия при достижении цели

Модели обучаются на исторических данных завершённых и отменённых закупок.

---

### Высокопроизводительная обработка данных (WebAssembly)

Для ускорения клиентских вычислений платформа использует **Rust + WebAssembly**:

| Функция | Назначение |
|---------|-----------|
| `batch_process_procurements` | Пакетный расчёт прогресса, форматирование валюты, дней осталось |
| `search_procurements` | Нечёткий поиск с взвешенной оценкой релевантности |
| `sort_procurements` | Многопольная сортировка закупок |
| `aggregate_procurement_stats` | Агрегация статистики (счётчики, суммы, города) |
| `batch_process_messages` | Форматирование сообщений, вычисление дат |
| `search_messages` | Полнотекстовый поиск по сообщениям |
| `format_message_text` | Безопасное форматирование текста с защитой от XSS |
| `validate_procurement_form` | Многопольная валидация формы закупки |
| `format_currency` | Форматирование суммы в рублях с разделителями тысяч |
| `get_avatar_color` / `get_initials` | Цвет и инициалы аватара на основе хеша |

При невозможности загрузки WASM автоматически используются JavaScript-реализации этих же функций.

---

### Архитектура платформы

Платформа построена по принципу микросервисов:

```
+-------------------+  +-------------------+  +-------------------+  +-------------------+
|   Telegram Bot    |  |      VK Bot       |  | Mattermost Bot    |  |   WebSocket Chat  |
+-------------------+  +-------------------+  +-------------------+  +-------------------+
         |                      |                      |                        |
         v                      v                      v                        v
+------------------------------------------------------------------------------------+
|                        Message Router / Bot Service                                |
+------------------------------------------------------------------------------------+
                                         |
                                         v
+------------------------------------------------------------------------------------+
|                             Core API (Django)                                      |
|                   - Пользователи  - Закупки  - Платежи                             |
+------------------------------------------------------------------------------------+
                    |                                         |
                    v                                         v
          +----------------+                       +----------------+
          |   PostgreSQL   |                       |     Redis      |
          +----------------+                       +----------------+
```

**Компоненты системы:**
- **Core Django API** — основная бизнес-логика, REST-эндпоинты
- **Core Rust (Async)** — обработка WebSocket, функции реального времени
- **Bot Service** — обработчики команд, FSM, интерактивные клавиатуры
- **Telegram Adapter** — трансляция протокола для Telegram
- **VK Adapter** — трансляция протокола для ВКонтакте
- **Mattermost Adapter** — трансляция протокола для Mattermost
- **React Frontend** — веб-интерфейс: административная панель и личный кабинет пользователя
- **WASM Utilities** — высокопроизводительные вычисления на стороне клиента

**Варианты развёртывания:**
- **Один сервер** — все сервисы запускаются вместе через `docker-compose`
- **Два сервера** — для высоких нагрузок:
  - Сервер 1: WebSocket-чат + Redis
  - Сервер 2: API + Bot + Адаптеры + PostgreSQL

---

## Features

- **Multi-platform support**: Telegram, VK, Mattermost, WebSocket (extensible to other platforms)
- **User management**: Registration with 3 roles (Buyer, Organizer, Supplier)
- **Procurement system**: Create, join, and manage group purchases
- **Real-time chat**: WebSocket-based chat for each procurement
- **Payment integration**: Tochka Bank (Cyclops) - nominal account for secure transactions
- **Admin Panel**: Full-featured web-based admin panel for managing users, procurements, and payments
- **High-performance client-side processing**: Rust + WebAssembly for computationally intensive operations
- **Scalable architecture**: Microservices-based design

## Architecture

```
+-------------------+  +-------------------+  +-------------------+  +-------------------+
|   Telegram Bot    |  |      VK Bot       |  | Mattermost Bot    |  |   WebSocket Chat  |
+-------------------+  +-------------------+  +-------------------+  +-------------------+
         |                      |                      |                        |
         v                      v                      v                        v
+------------------------------------------------------------------------------------+
|                        Message Router / Bot Service                                |
+------------------------------------------------------------------------------------+
                                         |
                                         v
+------------------------------------------------------------------------------------+
|                             Core API (Django)                                      |
|                      - Users  - Procurements  - Payments                           |
+------------------------------------------------------------------------------------+
                    |                                         |
                    v                                         v
          +----------------+                       +----------------+
          |   PostgreSQL   |                       |     Redis      |
          +----------------+                       +----------------+
```

## Quick Start

### Prerequisites

- Docker and Docker Compose
- Telegram Bot Token (from @BotFather) - optional, for Telegram integration
- VK Group Access Token (from VK group settings) - optional, for VK integration
- Tochka Bank account with Cyclops integration (for payments)

### Setup

1. Clone the repository:
```bash
git clone <repository-url>
cd groupbuy-bot
```

2. Copy environment file and configure:
```bash
cp .env.example .env
# Edit .env with your settings
```

3. Start the services (migrations run automatically):
```bash
docker-compose up -d
```

Note: Database migrations are applied automatically when the core service starts.

5. Create admin user:
```bash
# Development:
docker-compose exec core python manage.py createsuperuser
# Production:
docker compose -f docker-compose.prod.yml exec django-admin python manage.py createsuperuser
```

## Development

### Local Development Setup

1. Create virtual environments for each service:
```bash
# Core API
cd core && python -m venv venv && source venv/bin/activate
pip install -r requirements.txt

# Bot
cd ../bot && python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
```

2. Start PostgreSQL and Redis:
```bash
docker-compose up -d postgres redis
```

3. Run Core API:
```bash
cd core
python manage.py migrate
python manage.py runserver
```

4. Run Bot (in another terminal):
```bash
cd bot
python main.py
```

### Running Tests

```bash
# Core API tests
cd core
pytest

# Bot tests
cd bot
pytest ../tests/test_bot_commands.py

# WASM utils tests (Rust)
cd wasm-utils
cargo test
```

### WebAssembly (WASM) Development

The project uses Rust + WebAssembly for high-performance client-side processing.
WASM functions provide significant speedup for batch data operations (search, sort,
aggregation) compared to JavaScript, especially with large datasets.

#### WASM Functions Available

| Function | Description | Use Case |
|----------|-------------|----------|
| `batch_process_procurements` | Batch compute progress, format currency, days left | Rendering procurement lists |
| `search_procurements` | Fuzzy search with weighted relevance scoring | Client-side search filtering |
| `sort_procurements` | Multi-field sorting (title, amount, deadline, etc.) | Client-side sorting |
| `aggregate_procurement_stats` | Statistics aggregation (counts, totals, cities) | Dashboard statistics |
| `batch_process_messages` | Format messages, compute dates, escape HTML | Chat message rendering |
| `search_messages` | Full-text search within messages | Message search |
| `format_message_text` | XSS-safe text formatting with URL detection | Chat message display |
| `validate_procurement_form` | Multi-field form validation | Form submission |
| `validate_phone` / `validate_email` | Input validation | Registration forms |
| `format_currency` | Russian ruble formatting with thousands separator | Price display |
| `get_avatar_color` / `get_initials` | Hash-based avatar colors and initials | User avatars |
| `benchmark_batch_processing` | Performance measurement | Benchmarking |

#### Building WASM

```bash
# Install wasm-pack (if not installed)
curl https://rustwasm.github.io/wasm-pack/installer/init.sh -sSf | sh

# Build WASM package
cd wasm-utils
wasm-pack build --target web --out-dir ../frontend-react/src/wasm-pkg

# Run Rust tests
cargo test
```

The WASM module is automatically loaded by the React frontend on startup.
All WASM functions have JavaScript fallbacks — if WASM fails to load,
the application gracefully falls back to equivalent JS implementations.

## Production Deployment

### Single Server Deployment

Use the production Docker Compose file:

```bash
docker-compose -f docker-compose.prod.yml up -d
```

### Lightweight Deployment (1 GB RAM)

For servers with limited memory (e.g. 1 GB RAM), use the two-step deployment: first start the microservice infrastructure with `docker-compose.light.yml`, then bring up the application stack with `docker-compose.prod.yml`.

**Why two steps?**  
`docker-compose.light.yml` starts Kafka, Zookeeper, Centrifugo, and the microservices (gateway, auth, purchase, etc.) with strict memory limits. `docker-compose.prod.yml` starts the main application (core Rust API, Django admin, bot, frontend, nginx). Both files share the same `groupbuy-network` Docker network so all containers can communicate.

**Step 1 — Start infrastructure and microservices:**
```bash
cp .env.example .env   # fill in secrets
docker compose -f docker-compose.light.yml up -d --build
```

**Step 2 — Start the application layer:**
```bash
docker compose -f docker-compose.prod.yml up -d
```

> **Note:** Run Step 1 before Step 2 so that postgres and redis are healthy before the `core` container starts. The volumes (`postgres_data`, `redis_data`) are shared between both files.

> **Important:** The two compose files use the same `groupbuy-network` Docker network. Do **not** run them simultaneously on separate Docker networks or containers will not be able to reach each other.

### Two-Server Deployment

For high-load scenarios, the application supports a two-server architecture:
- **Server 1 (Chat)**: Handles real-time WebSocket connections
- **Server 2 (API/Bot)**: Handles business logic and data

On Server 1 (Chat):
```bash
docker-compose -f docker-compose.two-server.yml up -d websocket-server redis-chat nginx-chat
```

On Server 2 (API):
```bash
docker-compose -f docker-compose.two-server.yml up -d core bot telegram-adapter vk-adapter postgres redis-api nginx-api
```

Configure `CORE_API_URL` on Server 1 to point to Server 2's API endpoint.

## Platform Integration

### Telegram Integration

The bot supports full Telegram integration with the following features:
- Commands and text message handling
- Inline keyboards for interactive menus
- Payment integration via callback buttons
- Real-time notifications

**Setup:**
1. Create a bot via [@BotFather](https://t.me/BotFather)
2. Get your bot token
3. Add `TELEGRAM_TOKEN` to your `.env` file
4. Start the services with `docker-compose up -d`

### Mattermost Integration

The bot supports Mattermost integration, allowing users to interact with the GroupBuy platform through any self-hosted Mattermost server.

> **Подробное руководство по настройке (на русском):** [docs/mattermost-setup.md](./docs/mattermost-setup.md)

**How it works:**

The Mattermost adapter uses two Mattermost integration primitives:
- **Outgoing Webhooks** – Mattermost sends user messages to the adapter's HTTP endpoint (`POST /webhook`).
- **Incoming Webhooks** – The adapter posts replies back to Mattermost via an incoming webhook URL.
- **Slash Commands** – Users can trigger bot commands with `/command` syntax directly from the Mattermost input box.
- **Interactive Buttons** – The bot sends messages with clickable action buttons (equivalent to Telegram inline keyboards).

**Setup:**

1. Log in to your Mattermost server as an admin.
2. Go to **Main Menu → Integrations → Outgoing Webhooks** and create a new webhook:
   - **Content Type**: `application/x-www-form-urlencoded`
   - **Channel**: choose a channel or leave blank to handle all channels
   - **Trigger Words**: e.g. `/start`, `/help` (or leave blank to receive all messages)
   - **Callback URL**: `http://<your-server>:8002/webhook`
   - Copy the generated **Token**.
3. Go to **Integrations → Incoming Webhooks** and create a new webhook:
   - Choose the channel where bot replies should appear (or use `@username` per-message override)
   - Copy the generated **Webhook URL**.
4. (Optional but recommended) Go to **Integrations → Bot Accounts** and create a bot account for the GroupBuy bot:
   - Copy the generated **Personal Access Token** — this enables Direct Message replies and richer user lookups.
5. Add the following variables to your `.env` file:
   ```
   MATTERMOST_URL=https://your-mattermost-server.example.com
   MATTERMOST_TOKEN=<outgoing-webhook-token>
   MATTERMOST_WEBHOOK_URL=https://your-mattermost-server.example.com/hooks/<id>
   MATTERMOST_BOT_TOKEN=<bot-personal-access-token>   # optional, enables DM replies
   ```
6. Start the services:
   ```bash
   docker-compose up -d mattermost-adapter
   ```

**Available commands (identical to Telegram):**

| Command | Description |
|---|---|
| `/start` | Start the bot, see welcome message and main menu |
| `/help` | List all available commands |
| `/procurements` | Browse active procurements |
| `/my_procurements` | View procurements you joined or created |
| `/search` | Search procurements by keyword |
| `/create_procurement` | Create a new procurement (organizers only) |
| `/profile` | View and edit your profile |
| `/balance` | Check your balance |
| `/deposit` | Top up your balance |
| `/transactions` | Payment history |
| `/notifications` | View unread notifications |
| `/chat` | Enter a procurement chat |
| `/status` | Show bot health status |

**Interactive buttons:**

In Telegram the bot uses inline keyboard buttons. In Mattermost the same buttons are rendered as **message attachment actions** (clickable buttons below the message). Clicking a button in Mattermost triggers the same logic as tapping the equivalent Telegram button — for example, viewing procurement details, joining a procurement, or going back to the list.

**Important Notes:**
- The Mattermost adapter listens on port `8002` by default. Make sure this port is accessible from your Mattermost server.
- All bot commands and interactive flows work the same way as in Telegram — registration, joining procurements, payment, notifications, etc.
- When `MATTERMOST_BOT_TOKEN` is set the bot sends replies as **Direct Messages** to each user. Without it, replies go to the channel configured in the incoming webhook.
- The adapter is optional – other platform adapters (Telegram, VK) continue to work independently.

### VK Integration

The bot supports VK (VKontakte) integration with the same functionality as Telegram:
- All bot commands work identically in VK
- Inline keyboards converted to VK format
- Payment integration
- Real-time notifications

**Setup:**
1. Create a VK community (group) or use an existing one
2. Go to **Settings → API Usage → Access Tokens**
3. Create a new access token with the following permissions:
   - Messages (all permissions)
   - Community management
4. Enable **Messages** in Community settings → Messages → Community messages status: Enabled
5. Enable **Bot capabilities** in Messages settings
6. Add `VK_TOKEN` to your `.env` file with your group access token
7. Start the services with `docker-compose up -d`

**Important VK Configuration:**
- Your VK bot must be added to the group's messages
- Event types must be enabled: `message_new`, `message_event`
- Callback API URL should point to your server's VK webhook endpoint (if using webhooks)
- For development/testing, Long Poll API is used automatically

### Multi-Platform User Management

The system automatically handles users across multiple platforms:
- Each platform user is linked to a single internal user account
- Platform is identified by `platform` field: `telegram`, `vk`, or `mattermost`
- Users maintain their profile, balance, and procurements across all platforms
- Messages and notifications are delivered to the platform the user is currently using

### SSL Configuration

1. Place SSL certificates in `infrastructure/nginx/ssl/`
2. Update nginx configuration files to use HTTPS (uncomment SSL sections)

## Web Frontend

The application includes a Telegram-like web frontend accessible at the root URL (`/`).

Features:
- Responsive design matching Telegram's look and feel
- Real-time chat via WebSocket
- Personal cabinet for each role (Buyer, Organizer, Supplier)
- Procurement browsing with horizontal slider
- Dark/light theme support

## Admin Panel

The application includes a full-featured admin panel for managing all aspects of the platform.

### Accessing the Admin Panel

1. **Create an admin user** (if not already created):
```bash
# Development:
docker-compose exec core python manage.py createsuperuser
# Production:
docker compose -f docker-compose.prod.yml exec django-admin python manage.py createsuperuser
```

2. **Access the admin panel** at `/admin-panel/` in your browser

3. **Login** with your Django admin credentials

### Admin Panel Features

#### Dashboard
- Overview of key statistics (users, procurements, payments)
- User registration trends (today, week, month)
- Revenue statistics and breakdown
- Activity metrics (messages, notifications)

#### User Management
- View all registered users with filters (role, platform, status)
- Search users by name, email, phone, or platform ID
- Toggle user active/verified status
- Adjust user balance with transaction logging
- View user participation and organization history

#### Procurement Management
- View all procurements with status filters
- Change procurement status (draft, active, stopped, payment, completed, cancelled)
- Toggle featured status for promotions
- View procurement details and participants
- Filter by category, city, or featured status

#### Payment Monitoring
- View all payments with status filters
- View transaction history
- Payment summary and statistics
- Filter by payment type, status, or date range

#### Category Management
- Create, edit, and delete procurement categories
- Set category icons (emoji) and descriptions
- Organize categories with parent-child relationships

#### Message Management
- View all chat messages
- Search messages by content
- Soft delete/restore messages
- Send bulk notifications to all users

### Admin Panel Security

- Only Django staff users (is_staff=True) can access the admin panel
- Session-based authentication with CSRF protection
- All admin actions are logged for audit trails

### Admin API Endpoints

The admin panel is powered by a dedicated Admin API:

| Endpoint | Description |
|----------|-------------|
| `GET /api/admin/auth/` | Check authentication status |
| `POST /api/admin/auth/` | Login |
| `DELETE /api/admin/auth/` | Logout |
| `GET /api/admin/dashboard/` | Get dashboard statistics |
| `GET /api/admin/users/` | List users |
| `POST /api/admin/users/{id}/toggle_active/` | Toggle user active status |
| `POST /api/admin/users/{id}/toggle_verified/` | Toggle user verified status |
| `POST /api/admin/users/{id}/update_balance/` | Update user balance |
| `GET /api/admin/procurements/` | List procurements |
| `POST /api/admin/procurements/{id}/update_status/` | Update procurement status |
| `POST /api/admin/procurements/{id}/toggle_featured/` | Toggle featured status |
| `GET /api/admin/payments/` | List payments |
| `GET /api/admin/payments/summary/` | Get payment summary |
| `GET /api/admin/transactions/` | List transactions |
| `GET /api/admin/categories/` | List categories |
| `POST /api/admin/categories/` | Create category |
| `GET /api/admin/messages/` | List messages |
| `POST /api/admin/notifications/send_bulk/` | Send bulk notification |

## API Documentation

API documentation is available at `/api/docs/` when the server is running.

### Key Endpoints

#### Users
- `POST /api/users/` - Register user
- `GET /api/users/{id}/` - Get user details
- `GET /api/users/by_platform/` - Get user by platform

#### Procurements
- `GET /api/procurements/` - List procurements
- `POST /api/procurements/` - Create procurement
- `POST /api/procurements/{id}/join/` - Join procurement
- `GET /api/procurements/user/{user_id}/` - User's procurements

#### Payments
- `POST /api/payments/` - Create payment
- `GET /api/payments/{id}/status/` - Check payment status

#### Chat
- `GET /api/chat/messages/` - List messages
- `POST /api/chat/messages/` - Send message
- `WebSocket /ws/procurement/{id}/` - Real-time chat

## Bot Commands

### General
- `/start` - Start/register
- `/help` - Show help
- `/profile` - View profile
- `/balance` - Check balance

### Procurements
- `/procurements` - List active procurements
- `/my_procurements` - Your procurements
- `/create_procurement` - Create new (organizers only)

### Payments
- `/deposit` - Deposit to balance

## Environment Variables

| Variable | Description |
|----------|-------------|
| `TELEGRAM_TOKEN` | Telegram Bot API token (optional, for Telegram integration) |
| `VK_TOKEN` | VK Group Access Token (optional, for VK integration) |
| `MATTERMOST_URL` | Base URL of the Mattermost server (optional, for Mattermost integration) |
| `MATTERMOST_TOKEN` | Outgoing-webhook token from Mattermost (used to verify incoming requests) |
| `MATTERMOST_WEBHOOK_URL` | Incoming webhook URL for sending bot replies to Mattermost |
| `DB_NAME` | PostgreSQL database name |
| `DB_USER` | PostgreSQL user |
| `DB_PASSWORD` | PostgreSQL password |
| `DJANGO_SECRET_KEY` | Django secret key |
| `TOCHKA_API_URL` | Tochka Cyclops API URL |
| `TOCHKA_NOMINAL_ACCOUNT` | Nominal account number |
| `TOCHKA_PLATFORM_ID` | Platform ID in Cyclops |
| `TOCHKA_PRIVATE_KEY_PATH` | Path to private key for API signing |
| `JWT_SECRET` | JWT secret for WebSocket auth |

## CI/CD

This project uses GitHub Actions for continuous integration and deployment.

### Continuous Integration (CI)

The CI pipeline runs automatically on:
- Every push to the `main` branch
- Every pull request to the `main` branch

CI checks include:
- **Python linting**: Ruff linter and formatter for bot and adapter code
- **Rust build and tests**: Compilation and unit tests for the core-rust backend
- **WASM build**: Building WebAssembly utilities with wasm-pack
- **Frontend build**: Node.js build for the React frontend
- **Docker build**: Validation of all Dockerfile builds
- **Docker Compose validation**: Syntax check for all compose files

### Continuous Deployment (CD)

The CD pipeline is triggered:
- On every push to `main` - deploys to staging
- On version tags (`v*`) - deploys to production

#### Setting Up Deployment

1. **Configure GitHub Environments**:
   - Go to repository Settings → Environments
   - Create `staging` and `production` environments
   - Add environment-specific secrets and protection rules

2. **Configure Secrets**:
   Add the following secrets in repository Settings → Secrets:
   - `STAGING_SSH_KEY`: SSH private key for staging server
   - `STAGING_HOST`: Staging server hostname
   - `PRODUCTION_SSH_KEY`: SSH private key for production server
   - `PRODUCTION_HOST`: Production server hostname

3. **Customize Deployment Scripts**:
   Edit `.github/workflows/cd.yml` to add your deployment commands:
   ```yaml
   - name: Deploy to staging
     run: |
       ssh -i $SSH_KEY user@$STAGING_HOST "cd /app && docker compose pull && docker compose up -d"
   ```

### Manual Deployment

For manual deployment to a server:

```bash
# SSH to server
ssh user@your-server

# Navigate to project directory
cd /path/to/groupbuy-bot

# Pull latest changes
git pull origin main

# Pull and restart containers
docker compose -f docker-compose.prod.yml pull
docker compose -f docker-compose.prod.yml up -d

# Run migrations (if needed)
docker compose -f docker-compose.prod.yml exec core python manage.py migrate
```

### Creating a Release

1. Update version numbers in relevant files
2. Create and push a version tag:
   ```bash
   git tag v1.0.0
   git push origin v1.0.0
   ```
3. The CD pipeline will automatically build and push Docker images
4. The production deployment will be triggered (if configured)

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Run tests
5. Submit a pull request

## 🐳 Развёртывание в Docker (4 микросервиса)

Упрощённый стек из 4 сервисов, спроектированный согласно требованиям issue #33.

### Архитектура

| Контейнер | Технология | Назначение | Порт |
|---|---|---|---|
| `frontend-client` | Vite/React + Nginx | SPA личного кабинета | 80 |
| `backend-api` | FastAPI (Python) | Бизнес-логика, REST, Swagger | 8000 |
| `frontend-admin` | FastAPI + Jinja2 | Админ-панель | 8080 |
| `socket-broker` | FastAPI + Redis Pub/Sub | WebSocket-брокер | 8001 |
| `postgres` | PostgreSQL 16 | БД (общая) | — |
| `redis` | Redis 7 | Кэш + Pub/Sub | — |

**Ключевые свойства:**

- `backend-api` публикует события в Redis Pub/Sub вместо прямой отправки в сокеты — перезапуск бэкенда **не** разрывает WebSocket-соединения клиентов.
- `socket-broker` подписывается на каналы `room:<room_id>` и `room:admin` в Redis и рассылает сообщения всем подключённым клиентам.
- Swagger UI доступен по адресу `http://localhost:8000/api/docs`, OpenAPI-спецификация — в `docs/openapi.yaml`.

### Быстрый старт (чистая машина)

```bash
# 1. Клонировать репозиторий
git clone https://github.com/LPN1KoL/groupbuy-bot.git
cd groupbuy-bot

# 2. Создать файл окружения
cp .env.example .env
# Отредактируйте .env: задайте SECRET_KEY, DB_PASSWORD, REDIS_PASSWORD

# 3. Собрать и запустить
docker compose -f docker-compose.4services.yml up --build -d

# 4. Проверить состояние
docker compose -f docker-compose.4services.yml ps
```

### Адреса сервисов

| Адрес | Описание |
|---|---|
| `http://localhost` | Личный кабинет (React SPA) |
| `http://localhost:8080` | Админ-панель |
| `http://localhost:8000/api/docs` | Swagger UI |
| `http://localhost:8000/api/openapi.json` | OpenAPI JSON |
| `ws://localhost:8001/ws/{room_id}?token=<JWT>` | WebSocket подключение |

### Переменные окружения

| Переменная | По умолчанию | Описание |
|---|---|---|
| `DB_NAME` | `groupbuy` | Имя БД PostgreSQL |
| `DB_USER` | `postgres` | Пользователь БД |
| `DB_PASSWORD` | `postgres` | Пароль БД |
| `REDIS_PASSWORD` | `redis_secret` | Пароль Redis |
| `SECRET_KEY` | `change-me-in-production` | JWT-секрет (обязательно сменить!) |
| `CORS_ORIGINS` | `http://localhost,http://localhost:8080` | Разрешённые CORS-источники |

### WebSocket протокол

Подключение к `socket-broker`:
```
ws://localhost:8001/ws/{room_id}?token=<JWT>
```

После подключения клиент получает историю последних 50 сообщений комнаты, затем — живые события в формате:

```json
{
  "type": "message",
  "room": "42",
  "user_id": "123",
  "text": "Привет!",
  "timestamp": "2024-01-01T12:00:00+00:00"
}
```

Отправка сообщения:
```json
{ "text": "Текст сообщения" }
```

### Остановка и очистка

```bash
# Остановить контейнеры (данные сохраняются в named volumes)
docker compose -f docker-compose.4services.yml down

# Остановить и удалить volumes (сброс БД)
docker compose -f docker-compose.4services.yml down -v
```

## License

MIT License

# GroupBuy Bot — API Reference

Полный список API-запросов с описанием, параметрами и примерами.

---

## Содержание

- [Обзор архитектуры](#обзор-архитектуры)
- [Аутентификация](#аутентификация)
- [Rust Core API (Личный кабинет)](#rust-core-api-личный-кабинет)
  - [Здоровье системы (Rust)](#здоровье-системы-rust)
  - [Пользователи (Rust)](#пользователи-rust)
  - [Сессии пользователей (Rust)](#сессии-пользователей-rust)
  - [Закупки (Rust)](#закупки-rust)
  - [Участники закупок (Rust)](#участники-закупок-rust)
  - [Голосование за поставщика (Rust)](#голосование-за-поставщика-rust)
  - [Категории (Rust)](#категории-rust)
  - [Платежи (Rust)](#платежи-rust)
  - [Транзакции (Rust)](#транзакции-rust)
  - [Чат и сообщения (Rust)](#чат-и-сообщения-rust)
  - [Уведомления (Rust)](#уведомления-rust)
  - [WebSocket (Rust)](#websocket-rust)
- [Django Core API (устаревший / только для бота и ML)](#django-core-api-устаревший--только-для-бота-и-ml)
  - [Здоровье системы](#здоровье-системы)
  - [Пользователи](#пользователи)
  - [Сессии пользователей](#сессии-пользователей)
  - [Закупки](#закупки)
  - [Категории](#категории)
  - [Участники закупок](#участники-закупок)
  - [Платежи](#платежи)
  - [Транзакции](#транзакции)
  - [Чат и сообщения](#чат-и-сообщения)
  - [Уведомления](#уведомления)
  - [ML — Модели и предсказания](#ml--модели-и-предсказания)
  - [Административный API](#административный-api)
- [Микросервисы](#микросервисы)
  - [Auth Service (порт 4001)](#auth-service-порт-4001)
  - [Purchase Service (порт 4002)](#purchase-service-порт-4002)
  - [Payment Service (порт 4003)](#payment-service-порт-4003)
  - [Reputation Service (порт 4008)](#reputation-service-порт-4008)
  - [Search Service (порт 4007)](#search-service-порт-4007)
  - [Analytics Service (порт 4006)](#analytics-service-порт-4006)
  - [Notification Service (порт 4005)](#notification-service-порт-4005)
  - [Gateway (порт 3000)](#gateway-порт-3000)

---

> **Формат ответов микросервисов**: все NestJS и FastAPI сервисы возвращают ответы в едином формате:
> ```json
> { "success": true, "data": { ... } }
> ```
> при ошибках:
> ```json
> { "success": false, "error": "описание ошибки" }
> ```

---

## Обзор архитектуры

Система состоит из трёх уровней:

1. **Rust Core API** (`core-rust/`) — основной бэкенд сервис личного кабинета на Actix-web с PostgreSQL. Обрабатывает все запросы личного кабинета: пользователи, закупки, чат, платежи. Доступен по `/api/...` и имеет Swagger UI на `/api/docs/`.
2. **Django Core** (`core/`) — устаревший монолитный бэкенд с DRF. Используется для **Административного API** (`/api/admin/`) и ML-аналитики. **Не используется для запросов личного кабинета** — они переведены на Rust Core API.
3. **Микросервисы** — набор независимых сервисов (NestJS, Go, FastAPI), объединённых через Gateway.

> **Разделение:** Личный кабинет (пользовательский интерфейс) работает через **Rust Core API**. Административная панель работает через **Django Admin API** (`/api/admin/`).

Все запросы через Gateway направляются по префиксу пути к соответствующему микросервису.

---

## Аутентификация

- **Rust Core API**: JWT-токен в заголовке `Authorization: Bearer <token>`
- **Django Core**: JWT-токен в заголовке `Authorization: Bearer <token>`
- **Микросервисы**: JWT-токен в заголовке `Authorization: Bearer <token>` или через заголовок `x-user-id`
- **Webhook-эндпоинты**: без авторизации (проверяется подпись запроса)

---

## Rust Core API (Личный кабинет)

Основной бэкенд для личного кабинета. Базовый URL: `http://<host>:8000`

Swagger UI: `http://<host>:8000/api/docs/`
OpenAPI схема: `http://<host>:8000/api/schema/openapi.json`

---

### Здоровье системы (Rust)

#### `GET /health/`

Проверка состояния сервиса.

**Авторизация**: нет

**Ответ**: `OK`

---

### Пользователи (Rust)

#### `GET /api/users/`

Список всех пользователей.

**Параметры запроса**:
- `platform` (опционально) — фильтр по платформе
- `role` (опционально) — фильтр по роли

#### `POST /api/users/`

Создание нового пользователя.

**Тело запроса**:
```json
{
  "platform": "telegram",
  "platform_user_id": "123456",
  "first_name": "Иван",
  "last_name": "Иванов",
  "username": "ivan",
  "phone": "+79001234567",
  "email": "ivan@example.com",
  "role": "buyer",
  "language_code": "ru"
}
```

#### `GET /api/users/{id}/`

Получение пользователя по ID.

#### `PUT /api/users/{id}/` / `PATCH /api/users/{id}/`

Обновление данных пользователя.

#### `DELETE /api/users/{id}/`

Удаление пользователя.

#### `GET /api/users/by_platform/`

Поиск пользователя по платформе.

**Параметры**: `platform`, `platform_user_id`

#### `GET /api/users/by_email/`

Поиск по email. **Параметр**: `email`

#### `GET /api/users/by_phone/`

Поиск по телефону. **Параметр**: `phone`

#### `GET /api/users/check_exists/`

Проверка существования пользователя.

#### `GET /api/users/search/`

Полнотекстовый поиск пользователей (до 20 результатов).

**Параметр**: `q` — строка поиска

#### `GET /api/users/{id}/balance/`

Баланс пользователя со статистикой.

#### `POST /api/users/{id}/update_balance/`

Обновление баланса.

**Тело**:
```json
{"amount": 500.00, "operation": "add"}
```

#### `GET /api/users/{id}/role/`

Роль пользователя.

#### `GET /api/users/{id}/ws_token/`

Генерация JWT-токена для WebSocket (TTL 24 часа).

---

### Сессии пользователей (Rust)

#### `POST /api/users/sessions/set_state/`

Установка состояния диалога.

**Тело**:
```json
{"user_id": "uuid", "platform": "telegram", "state": "waiting_for_amount", "data": {}}
```

#### `POST /api/users/sessions/clear_state/`

Сброс состояния диалога.

---

### Закупки (Rust)

#### `GET /api/procurements/`

Список закупок.

**Параметры**: `status`, `city`

#### `POST /api/procurements/`

Создание закупки.

**Тело**:
```json
{
  "title": "Закупка",
  "description": "Описание",
  "organizer_id": "uuid",
  "city": "Москва",
  "target_amount": "100000.00",
  "deadline": "2026-06-01T00:00:00Z",
  "commission_percent": "5.00"
}
```

#### `GET /api/procurements/{id}/`

Детали закупки.

#### `PUT /api/procurements/{id}/` / `PATCH /api/procurements/{id}/`

Обновление закупки (только организатор).

#### `DELETE /api/procurements/{id}/`

Удаление закупки.

#### `GET /api/procurements/user/{user_id}/`

Закупки пользователя (организованные + участие).

**Ответ**:
```json
{"organized": [...], "participating": [...]}
```

#### `POST /api/procurements/{id}/join/`

Вступить в закупку.

**Тело**:
```json
{"user_id": "uuid", "amount": "5000.00", "quantity": "2", "notes": ""}
```

#### `POST /api/procurements/{id}/leave/`

Покинуть закупку.

**Тело**:
```json
{"user_id": "uuid"}
```

#### `POST /api/procurements/{id}/check_access/`

Проверить доступ пользователя к чату закупки.

**Тело**: `{"user_id": "uuid"}`

**Ответ**:
```json
{"has_access": true, "is_organizer": false, "is_participant": true}
```

#### `POST /api/procurements/{id}/update_status/`

Смена статуса закупки (только организатор).

**Тело**:
```json
{"organizer_id": "uuid", "status": "active"}
```

Допустимые статусы: `draft`, `active`, `stopped`, `payment`, `completed`, `cancelled`

#### `POST /api/procurements/{id}/stop_amount/`

Организатор останавливает приём новых участников (переводит в статус `stopped`).

#### `POST /api/procurements/{id}/approve_supplier/`

Организатор утверждает поставщика (переводит в статус `payment`).

**Тело**: `{"supplier_id": "uuid"}`

#### `GET /api/procurements/{id}/receipt_table/`

Таблица для отправки поставщику (участники со статусом `confirmed`/`paid`).

**Ответ**:
```json
{
  "rows": [{"user_id": "uuid", "quantity": "2", "amount": "5000.00", "notes": "", "status": "confirmed"}],
  "total_amount": "5000.00",
  "commission_percent": "5.00",
  "commission_amount": "250.00"
}
```

#### `POST /api/procurements/{id}/close/`

Организатор закрывает завершённую закупку (переводит в `completed`).

#### `POST /api/procurements/{id}/invite/`

Организатор отправляет приглашение по email.

**Тело**: `{"organizer_id": "uuid", "email": "user@example.com"}`

---

### Участники закупок (Rust)

#### `GET /api/procurements/{id}/participants/`

Список активных участников закупки.

#### `POST /api/procurements/{id}/add_participant/`

Организатор добавляет участника вручную.

**Тело**:
```json
{"organizer_id": "uuid", "user_id": "uuid", "amount": "5000.00", "quantity": "2", "notes": ""}
```

#### `PATCH /api/procurements/participants/{id}/update_status/`

Обновление статуса участника.

**Тело**: `{"status": "confirmed"}`

Допустимые статусы: `pending`, `confirmed`, `paid`, `completed`, `cancelled`

---

### Голосование за поставщика (Rust)

#### `POST /api/procurements/{id}/cast_vote/`

Голосование за поставщика (один голос на закупку, можно изменить).

**Тело**:
```json
{"voter_id": "uuid", "supplier_id": "uuid", "comment": "Хороший поставщик"}
```

#### `GET /api/procurements/{id}/vote_results/`

Результаты голосования.

**Ответ**:
```json
{
  "results": [{"supplier_id": "uuid", "vote_count": 5, "percentage": 62.5, "total_votes": 8}],
  "total_votes": 8
}
```

#### `POST /api/procurements/{id}/close_vote/`

Подтверждение участника о закрытии голосования.

**Тело**: `{"user_id": "uuid"}`

**Ответ**: `{"confirmed": 3, "total": 5, "user_id": "uuid"}`

#### `GET /api/procurements/{id}/vote_close_status/`

Статус закрытия голосования.

**Ответ**: `{"confirmed_users": ["uuid1", "uuid2"], "confirmed": 2, "total": 5}`

---

### Категории (Rust)

#### `GET /api/procurements/categories/`

Список активных категорий.

---

### Платежи (Rust)

#### `GET /api/payments/`

Список платежей.

**Параметры**: `user_id`, `payment_type`, `status`

#### `POST /api/payments/`

Создание платежа (депозит).

**Тело**:
```json
{"user_id": "uuid", "payment_type": "deposit", "amount": "1000.00", "description": "Пополнение"}
```

#### `GET /api/payments/{id}/`

Детали платежа.

#### `GET /api/payments/{id}/status/`

Статус платежа.

#### `POST /api/payments/{id}/simulate_success/`

Симуляция успешного платежа (для разработки/тестирования).

#### `POST /api/payments/webhook/`

Webhook от платёжного провайдера (Tochka или YooKassa, определяется автоматически).

---

### Транзакции (Rust)

#### `GET /api/payments/transactions/`

История транзакций.

**Параметры**: `user_id`, `transaction_type`

Типы: `deposit`, `withdrawal`, `procurement_join`, `refund`

#### `GET /api/payments/transactions/{id}/`

Детали транзакции.

#### `GET /api/payments/transactions/summary/`

Сводка транзакций пользователя.

**Параметр**: `user_id`

**Ответ**:
```json
{
  "current_balance": "4750.00",
  "total_deposited": "5000.00",
  "total_withdrawn": "0.00",
  "total_refunded": "0.00",
  "transaction_count": 2
}
```

---

### Чат и сообщения (Rust)

#### `GET /api/chat/messages/`

Список сообщений.

**Параметры**: `procurement` (ID закупки), `user`

#### `POST /api/chat/messages/`

Отправить сообщение.

**Тело**:
```json
{"procurement": 1, "user": "uuid", "text": "Привет!", "message_type": "text"}
```

#### `POST /api/chat/messages/mark_read/`

Пометить сообщения как прочитанные.

**Тело**: `{"user_id": "uuid", "procurement_id": 1}`

#### `GET /api/chat/messages/unread_count/`

Количество непрочитанных сообщений.

**Параметры**: `user_id` (обязательный), `procurement_id` (опционально)

**Ответ**: `{"unread_count": 5}` или `{"unread_count": 3, "procurement_id": 1}`

---

### Уведомления (Rust)

#### `GET /api/chat/notifications/`

Список уведомлений.

**Параметр**: `user_id`

#### `POST /api/chat/notifications/`

Создать уведомление.

**Тело**:
```json
{"user_id": "uuid", "notification_type": "info", "title": "Заголовок", "message": "Текст", "procurement_id": 1}
```

#### `POST /api/chat/notifications/mark_all_read/`

Пометить все уведомления пользователя как прочитанные.

**Тело**: `{"user_id": "uuid"}`

**Ответ**: `{"updated": 5}`

#### `POST /api/chat/notifications/{id}/mark_read/`

Пометить одно уведомление как прочитанное.

---

### WebSocket (Rust)

#### `WS /ws/chat/`

WebSocket соединение для чата в реальном времени. Требует токен из `GET /api/users/{id}/ws_token/`.

---

## Django Core API (устаревший / только для бота и ML)

> **Примечание:** Запросы личного кабинета переведены на **Rust Core API**. Django Core API используется только для Административного API и ML-аналитики.

Базовый URL: `http://<host>:<port>`

---

### Здоровье системы

#### `GET /health/`

Проверка состояния сервиса.

**Авторизация**: нет

**Ответ**:
```json
{"status": "healthy"}
```

#### `GET /api/schema/`

OpenAPI-схема.

**Авторизация**: нет

#### `GET /api/docs/`

Swagger UI.

**Авторизация**: нет

---

### Пользователи

Базовый путь: `/api/users/`

#### `GET /api/users/`

Список пользователей.

**Параметры запроса**:

| Параметр | Тип | Описание |
|---|---|---|
| `role` | string | Фильтр по роли (`organizer`, `buyer`, ...) |
| `platform` | string | Фильтр по платформе (`telegram`, `vk`, ...) |

**Пример запроса**:
```http
GET /api/users/?platform=telegram&role=organizer
```

**Пример ответа**:
```json
[
  {
    "id": 1,
    "username": "user123",
    "email": "user@example.com",
    "role": "organizer",
    "platform": "telegram",
    "platform_user_id": "123456789",
    "balance": "100.00",
    "is_active": true,
    "is_verified": false,
    "created_at": "2024-01-01T10:00:00Z"
  }
]
```

---

#### `POST /api/users/`

Регистрация нового пользователя.

**Авторизация**: нет

**Поля запроса**:

| Поле | Тип | Обязательное | Описание |
|---|---|---|---|
| `platform` | string | **да** | Платформа: `telegram`, `vk` |
| `platform_user_id` | string | **да** | ID пользователя на платформе |
| `username` | string | **да** | Имя пользователя |
| `first_name` | string | нет | Имя (по умолчанию `""`) |
| `last_name` | string | нет | Фамилия (по умолчанию `""`) |
| `phone` | string | нет | Номер телефона (по умолчанию `""`; если передаётся — должен начинаться с `+`) |
| `email` | string (email) | нет | Электронная почта (по умолчанию `""`) |
| `role` | string | нет | Роль: `organizer`, `buyer`, `supplier` (по умолчанию `buyer`) |
| `language_code` | string | нет | Языковой код (например, `ru`, `en`) |
| `selfie_file_id` | string | нет | ID файла с селфи (только запись, в ответе не возвращается) |

**Пример запроса**:
```json
{
  "platform": "telegram",
  "platform_user_id": "123456789",
  "username": "user123",
  "first_name": "Иван",
  "last_name": "Петров",
  "phone": "+79001234567",
  "email": "user@example.com",
  "role": "buyer",
  "language_code": "ru"
}
```

**Ответ** (`201 Created`):
```json
{
  "id": 42,
  "platform": "telegram",
  "platform_user_id": "123456789",
  "username": "user123",
  "first_name": "Иван",
  "last_name": "Петров",
  "phone": "+79001234567",
  "email": "user@example.com",
  "role": "buyer",
  "language_code": "ru",
  "balance": "0.00",
  "is_active": true,
  "created_at": "2024-01-15T12:00:00Z"
}
```

---

#### `GET /api/users/{id}/`

Данные пользователя по ID.

**Пример**:
```http
GET /api/users/42/
```

**Ответ**:
```json
{
  "id": 42,
  "username": "user123",
  "email": "user@example.com",
  "role": "buyer",
  "platform": "telegram",
  "platform_user_id": "123456789",
  "balance": "250.00",
  "is_active": true,
  "is_verified": true,
  "created_at": "2024-01-15T12:00:00Z",
  "updated_at": "2024-02-10T08:30:00Z"
}
```

---

#### `PUT /api/users/{id}/`

Обновление профиля пользователя.

**Авторизация**: владелец или администратор

**Поля запроса** (все необязательные при PATCH; при PUT — все обязательные):

| Поле | Тип | Описание |
|---|---|---|
| `first_name` | string | Имя |
| `last_name` | string | Фамилия |
| `phone` | string | Номер телефона |
| `email` | string (email) | Электронная почта |
| `role` | string | Роль: `organizer`, `buyer`, `supplier` |

**Пример запроса**:
```json
{
  "first_name": "Иван",
  "last_name": "Петров",
  "phone": "+79001234567",
  "email": "new@example.com",
  "role": "organizer"
}
```

---

#### `DELETE /api/users/{id}/`

Удаление пользователя.

**Авторизация**: владелец или администратор

---

#### `GET /api/users/by_platform/`

Поиск пользователя по платформе и идентификатору.

**Параметры запроса** (обязательные):

| Параметр | Тип | Описание |
|---|---|---|
| `platform` | string | Платформа (`telegram`, `vk`) |
| `platform_user_id` | string | ID пользователя на платформе |

**Пример**:
```http
GET /api/users/by_platform/?platform=telegram&platform_user_id=123456789
```

**Ответ**:
```json
{
  "id": 42,
  "username": "user123",
  "platform": "telegram",
  "platform_user_id": "123456789"
}
```

---

#### `GET /api/users/by_email/`

Поиск пользователя по email.

**Параметры запроса**:

| Параметр | Тип | Описание |
|---|---|---|
| `email` | string | Email пользователя |

**Пример**:
```http
GET /api/users/by_email/?email=user@example.com
```

---

#### `GET /api/users/by_phone/`

Поиск пользователя по телефону.

**Параметры запроса**:

| Параметр | Тип | Описание |
|---|---|---|
| `phone` | string | Номер телефона |

---

#### `GET /api/users/search/`

Полнотекстовый поиск пользователей.

**Параметры запроса**:

| Параметр | Тип | Описание |
|---|---|---|
| `q` | string | Строка поиска (обязательно) |

**Пример**:
```http
GET /api/users/search/?q=иван
```

**Ответ**:
```json
[
  {"id": 10, "username": "ivan123", "email": "ivan@example.com"},
  {"id": 25, "username": "ivanpetrov", "email": "petrov@example.com"}
]
```

Максимум 20 результатов.

---

#### `GET /api/users/check_exists/`

Проверка существования пользователя.

**Параметры запроса**:

| Параметр | Тип | Описание |
|---|---|---|
| `platform` | string | Платформа |
| `platform_user_id` | string | ID пользователя |

**Пример**:
```http
GET /api/users/check_exists/?platform=telegram&platform_user_id=123456789
```

**Ответ**:
```json
{"exists": true}
```

---

#### `GET /api/users/{id}/balance/`

Баланс пользователя.

**Авторизация**: публичный

**Пример**:
```http
GET /api/users/42/balance/
```

**Ответ**:
```json
{
  "balance": "250.00",
  "total_deposited": "500.00",
  "total_spent": "200.00",
  "available": "250.00"
}
```

---

#### `POST /api/users/{id}/update_balance/`

Изменение баланса пользователя.

**Авторизация**: владелец или администратор

**Тело запроса**:
```json
{
  "amount": 100.00
}
```

**Ответ**:
```json
{
  "balance": 350.00,
  "message": "Balance updated successfully"
}
```

---

#### `GET /api/users/{id}/role/`

Получить роль пользователя.

**Ответ**:
```json
{
  "role": "organizer",
  "role_display": "Организатор"
}
```

---

#### `GET /api/users/{id}/ws_token/`

Получить WebSocket JWT-токен для пользователя.

**Авторизация**: владелец или администратор

**Ответ**:
```json
{
  "token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "expires_in": 86400
}
```

---

### Сессии пользователей

#### `GET /api/users/sessions/`

Список сессий.

**Параметры запроса**:

| Параметр | Тип | Описание |
|---|---|---|
| `user_id` | integer | ID пользователя |

---

#### `POST /api/users/sessions/`

Создать сессию.

**Авторизация**: требуется

**Поля запроса**:

| Поле | Тип | Обязательное | Описание |
|---|---|---|---|
| `dialog_type` | string | **да** | Тип диалога (например, `procurement_creation`) |
| `dialog_state` | string | нет | Текущее состояние диалога |
| `dialog_data` | object | нет | Данные диалога (произвольный JSON) |
| `expires_at` | datetime | нет | Время истечения сессии (ISO 8601) |

**Пример запроса**:
```json
{
  "dialog_type": "procurement_creation",
  "dialog_state": "waiting_title",
  "dialog_data": {"step": 1},
  "expires_at": "2024-01-16T12:00:00Z"
}
```

---

#### `GET /api/users/sessions/{id}/`

Получить сессию по ID.

---

#### `POST /api/users/sessions/set_state/`

Установить состояние диалога пользователя.

**Тело запроса**:
```json
{
  "user_id": 42,
  "dialog_type": "procurement_creation",
  "dialog_state": "waiting_title",
  "dialog_data": {
    "step": 1,
    "draft": {}
  }
}
```

**Ответ**: обновлённая сессия

---

#### `POST /api/users/sessions/clear_state/`

Очистить состояние сессии.

**Тело запроса**:
```json
{
  "user_id": 42
}
```

**Ответ**:
```json
{"message": "Session cleared"}
```

---

### Закупки

Базовый путь: `/api/procurements/`

#### `GET /api/procurements/`

Список закупок с фильтрами.

**Параметры запроса**:

| Параметр | Тип | Описание |
|---|---|---|
| `status` | string | Статус: `draft`, `open`, `closed`, ... |
| `category` | integer | ID категории |
| `city` | string | Город |
| `organizer` | integer | ID организатора |
| `active_only` | boolean | Только активные |
| `search` | string | Поиск по названию/описанию |
| `ordering` | string | Сортировка: `created_at`, `-created_at`, `deadline` |

**Пример**:
```http
GET /api/procurements/?status=open&city=Москва&ordering=-created_at
```

**Ответ**:
```json
[
  {
    "id": 101,
    "title": "Закупка зимней одежды",
    "description": "Куртки и пуховики оптом",
    "status": "open",
    "category": 5,
    "organizer_id": 42,
    "current_amount": "15000.00",
    "target_amount": "50000.00",
    "commission_percent": "3.00",
    "city": "Москва",
    "unit": "шт",
    "deadline": "2024-03-01T00:00:00Z",
    "participants_count": 12,
    "created_at": "2024-01-10T09:00:00Z"
  }
]
```

---

#### `POST /api/procurements/`

Создать закупку.

**Авторизация**: требуется

**Поля запроса**:

| Поле | Тип | Обязательное | Описание |
|---|---|---|---|
| `title` | string (макс. 200) | **да** | Название закупки |
| `description` | string | **да** | Описание закупки |
| `category` | integer | **да** | ID категории |
| `organizer` | integer | **да** | ID организатора |
| `city` | string (макс. 100) | **да** | Город |
| `target_amount` | decimal (12,2) | **да** | Целевая сумма закупки |
| `deadline` | datetime | **да** | Дедлайн (ISO 8601) |
| `delivery_address` | string | нет | Адрес доставки |
| `stop_at_amount` | decimal (12,2) | нет | Сумма автоостановки приёма заявок |
| `unit` | string (макс. 20) | нет | Единица измерения (по умолчанию `units`): `кг`, `шт`, `л` и др. |
| `price_per_unit` | decimal (10,2) | нет | Цена за единицу товара |
| `commission_percent` | decimal (4,2) | нет | Комиссия организатора в % (1–4; по умолчанию `0`) |
| `min_quantity` | decimal (10,2) | нет | Минимальное общее количество для запуска |
| `payment_deadline` | datetime | нет | Дедлайн оплаты (ISO 8601) |
| `image_url` | string (URL) | нет | Ссылка на изображение |

**Пример запроса**:
```json
{
  "title": "Закупка зимней одежды",
  "description": "Куртки и пуховики оптом",
  "category": 5,
  "organizer": 42,
  "city": "Москва",
  "target_amount": "50000.00",
  "deadline": "2024-03-01T00:00:00Z",
  "delivery_address": "ул. Ленина, 1",
  "stop_at_amount": "60000.00",
  "unit": "шт",
  "price_per_unit": "2500.00",
  "commission_percent": "3.00",
  "min_quantity": "10",
  "payment_deadline": "2024-03-15T00:00:00Z",
  "image_url": "https://example.com/image.jpg"
}
```

**Ответ** (`201 Created`): объект закупки

---

#### `GET /api/procurements/{id}/`

Детальная информация о закупке.

**Авторизация**: публичный

---

#### `PUT /api/procurements/{id}/`

Обновить закупку.

**Авторизация**: организатор

**Поля запроса**: те же, что и для `POST /api/procurements/`. При PATCH все поля необязательные; при PUT — обязательные присутствуют в соответствии с таблицей выше.

---

#### `DELETE /api/procurements/{id}/`

Удалить закупку.

**Авторизация**: организатор

---

#### `GET /api/procurements/{id}/participants/`

Список активных участников закупки.

**Авторизация**: публичный

**Пример**:
```http
GET /api/procurements/101/participants/
```

**Ответ**:
```json
[
  {
    "id": 1,
    "user_id": 10,
    "procurement_id": 101,
    "quantity": 2,
    "amount": "2500.00",
    "status": "active",
    "notes": "Размер L"
  }
]
```

---

#### `POST /api/procurements/{id}/join/`

Присоединиться к закупке.

**Авторизация**: требуется

**Поля запроса**:

| Поле | Тип | Обязательное | Описание |
|---|---|---|---|
| `user_id` | integer | **да** | ID пользователя |
| `amount` | decimal (12,2) | **да** | Сумма участия |
| `quantity` | decimal (10,2) | нет | Количество единиц товара (по умолчанию `1`) |
| `notes` | string | нет | Примечания (особые пожелания) |

**Пример запроса**:
```json
{
  "user_id": "10",
  "quantity": 2,
  "amount": "2500.00",
  "notes": "Размер L"
}
```

**Ответ** (`201 Created`): объект участника

---

#### `POST /api/procurements/{id}/add_participant/`

Добавить участника (от имени организатора).

**Авторизация**: организатор

**Поля запроса**:

| Поле | Тип | Обязательное | Описание |
|---|---|---|---|
| `user_id` | integer | **да** | ID добавляемого пользователя |
| `organizer_id` | integer | **да** | ID организатора (подтверждение прав) |
| `amount` | decimal (12,2) | **да** | Сумма участия |
| `quantity` | decimal (10,2) | нет | Количество единиц товара (по умолчанию `1`) |
| `notes` | string | нет | Примечания |

**Пример запроса**:
```json
{
  "organizer_id": "42",
  "user_id": "10",
  "quantity": 2,
  "amount": "2500.00",
  "notes": "Добавлен вручную"
}
```

---

#### `POST /api/procurements/{id}/leave/`

Покинуть закупку.

**Авторизация**: требуется

**Поля запроса**:

| Поле | Тип | Обязательное | Описание |
|---|---|---|---|
| `user_id` | integer | **да** | ID пользователя, покидающего закупку |

**Пример запроса**:
```json
{
  "user_id": "10"
}
```

**Ответ**:
```json
{"message": "Successfully left the procurement"}
```

---

#### `GET /api/procurements/user/{user_id}/`

Закупки пользователя (организованные и участие).

**Авторизация**: публичный

**Пример**:
```http
GET /api/procurements/user/42/
```

**Ответ**:
```json
{
  "organized": [
    {"id": 101, "title": "Закупка зимней одежды", "status": "open"}
  ],
  "participating": [
    {"id": 55, "title": "Закупка электроники", "status": "closed"}
  ]
}
```

---

#### `POST /api/procurements/{id}/check_access/`

Проверить доступ пользователя к закупке.

**Авторизация**: требуется

**Поля запроса**:

| Поле | Тип | Обязательное | Описание |
|---|---|---|---|
| `user_id` | integer | **да** | ID проверяемого пользователя |

**Пример запроса**:
```json
{
  "user_id": "10"
}
```

**Ответ**:
```json
{"access": true}
```

---

#### `POST /api/procurements/{id}/update_status/`

Изменить статус закупки.

**Авторизация**: организатор

**Поля запроса**:

| Поле | Тип | Обязательное | Описание |
|---|---|---|---|
| `user_id` | integer | **да** | ID организатора |
| `status` | string | **да** | Новый статус: `draft`, `active`, `stopped`, `payment`, `completed`, `cancelled` |

**Пример запроса**:
```json
{
  "user_id": "42",
  "status": "active"
}
```

**Ответ**:
```json
{
  "status": "closed",
  "status_display": "Закрыта"
}
```

---

#### `POST /api/procurements/{id}/cast_vote/`

Проголосовать за поставщика.

**Авторизация**: требуется

**Поля запроса**:

| Поле | Тип | Обязательное | Описание |
|---|---|---|---|
| `voter_id` | integer | **да** | ID голосующего пользователя |
| `supplier_id` | integer | **да** | ID поставщика (пользователь с ролью `supplier`) |
| `comment` | string | нет | Комментарий к голосу |

**Пример запроса**:
```json
{
  "voter_id": 10,
  "supplier_id": 55,
  "comment": "Хороший поставщик"
}
```

**Ответ**: объект голоса

---

#### `GET /api/procurements/{id}/vote_results/`

Результаты голосования.

**Авторизация**: публичный

**Ответ**:
```json
{
  "procurement_id": 101,
  "total_votes": 8,
  "results": [
    {"supplier_id": "supplier_abc", "votes": 5, "percent": 62.5},
    {"supplier_id": "supplier_xyz", "votes": 3, "percent": 37.5}
  ]
}
```

---

#### `POST /api/procurements/{id}/close_vote/`

Инициировать закрытие голосования.

**Авторизация**: требуется

**Поля запроса**:

| Поле | Тип | Обязательное | Описание |
|---|---|---|---|
| `user_id` | integer | **да** | ID пользователя, подтверждающего закрытие голосования |

**Пример запроса**:
```json
{
  "user_id": "10"
}
```

**Ответ**:
```json
{
  "procurement_id": 101,
  "closed_by": [10, 15, 22],
  "close_count": 3,
  "total_participants": 12
}
```

---

#### `GET /api/procurements/{id}/vote_close_status/`

Статус закрытия голосования.

**Авторизация**: публичный

**Ответ**:
```json
{
  "procurement_id": 101,
  "closed_by": [10, 15],
  "close_count": 2,
  "total_participants": 12
}
```

---

#### `POST /api/procurements/{id}/approve_supplier/`

Утвердить победившего поставщика.

**Авторизация**: организатор

**Поля запроса**:

| Поле | Тип | Обязательное | Описание |
|---|---|---|---|
| `supplier_id` | integer | **да** | ID поставщика (пользователь с ролью `supplier`) |

**Пример запроса**:
```json
{
  "supplier_id": 55
}
```

**Ответ**:
```json
{
  "message": "Supplier approved",
  "supplier_id": "supplier_abc",
  "status": "supplier_selected"
}
```

---

#### `POST /api/procurements/{id}/stop_amount/`

Остановить приём заявок (по сумме).

**Авторизация**: организатор

**Ответ**:
```json
{
  "message": "Procurement stopped by amount threshold",
  "status": "amount_reached",
  "participants": [...]
}
```

---

#### `GET /api/procurements/{id}/receipt_table/`

Таблица чека для закупки.

**Авторизация**: организатор

**Ответ**:
```json
{
  "rows": [
    {
      "user_id": 10,
      "username": "user123",
      "quantity": 2,
      "amount": "2500.00"
    }
  ],
  "totals": {
    "total_quantity": 25,
    "total_amount": "31250.00",
    "commission": "937.50",
    "net_amount": "30312.50"
  }
}
```

---

#### `POST /api/procurements/{id}/send_to_supplier/`

Отправить закупку поставщику.

**Авторизация**: организатор

**Поля запроса**:

| Поле | Тип | Обязательное | Описание |
|---|---|---|---|
| `organizer_id` | integer | **да** | ID организатора |
| `idempotency_key` | string | **да** | Уникальный ключ идемпотентности (для предотвращения дублирования) |
| `supplier_api_url` | string | нет | URL API поставщика для отправки заказа |
| `job_type` | string | нет | Тип задания (по умолчанию `receipt_table`): `receipt_table`, `order_placement` |

**Пример запроса**:
```json
{
  "organizer_id": "42",
  "supplier_api_url": "https://supplier.example.com/api/orders",
  "idempotency_key": "unique-key-12345",
  "job_type": "order_placement"
}
```

**Ответ** (`200 OK` или `202 Accepted`):
```json
{
  "success": true,
  "job_id": 78,
  "status": "queued",
  "retry_count": 0
}
```

**При превышении лимита** (`429 Too Many Requests`):
```json
{"detail": "Too many requests. Please retry later."}
```

---

#### `POST /api/procurements/{id}/close/`

Закрыть закупку.

**Авторизация**: организатор

**Тело запроса**: не требуется.

**Ответ**:
```json
{
  "message": "Procurement closed successfully",
  "status": "closed"
}
```

---

#### `POST /api/procurements/{id}/invite/`

Пригласить пользователя по email.

**Авторизация**: организатор

**Поля запроса**:

| Поле | Тип | Обязательное | Описание |
|---|---|---|---|
| `email` | string (email) | **да** | Email приглашаемого пользователя |
| `organizer_id` | integer | нет | ID организатора |

**Пример запроса**:
```json
{
  "organizer_id": "42",
  "email": "newuser@example.com"
}
```

**Ответ**:
```json
{
  "message": "Invitation sent",
  "procurement_id": 101,
  "invited_email": "newuser@example.com"
}
```

---

### Категории

Базовый путь: `/api/procurements/categories/`

#### `GET /api/procurements/categories/`

Список категорий.

**Параметры запроса**:

| Параметр | Тип | Описание |
|---|---|---|
| `parent` | integer | ID родительской категории (для вложенных) |

**Ответ**:
```json
[
  {
    "id": 1,
    "name": "Одежда",
    "parent": null,
    "children": [
      {"id": 5, "name": "Верхняя одежда", "parent": 1}
    ]
  }
]
```

---

#### `POST /api/procurements/categories/`

Создать категорию.

**Авторизация**: администратор

**Поля запроса**:

| Поле | Тип | Обязательное | Описание |
|---|---|---|---|
| `name` | string (макс. 100) | **да** | Название категории |
| `description` | string | нет | Описание категории |
| `parent` | integer | нет | ID родительской категории (для вложенных категорий) |
| `icon` | string (макс. 50) | нет | Иконка (emoji или название иконки) |
| `is_active` | boolean | нет | Активна ли категория (по умолчанию `true`) |

**Пример запроса**:
```json
{
  "name": "Электроника",
  "description": "Электронные устройства и гаджеты",
  "parent": null,
  "icon": "📱",
  "is_active": true
}
```

---

#### `GET /api/procurements/categories/{id}/`

Детали категории.

#### `PUT /api/procurements/categories/{id}/`

Обновить категорию. **Авторизация**: администратор

#### `DELETE /api/procurements/categories/{id}/`

Удалить категорию. **Авторизация**: администратор

---

### Участники закупок

Базовый путь: `/api/procurements/participants/`

#### `GET /api/procurements/participants/`

Список участников.

**Параметры запроса**:

| Параметр | Тип | Описание |
|---|---|---|
| `procurement` | integer | ID закупки |
| `user` | integer | ID пользователя |

---

#### `POST /api/procurements/participants/`

Создать участие. **Авторизация**: требуется

**Поля запроса**:

| Поле | Тип | Обязательное | Описание |
|---|---|---|---|
| `procurement` | integer | **да** | ID закупки |
| `user` | integer | **да** | ID пользователя |
| `amount` | decimal (12,2) | **да** | Сумма участия |
| `quantity` | decimal (10,2) | нет | Количество единиц товара (по умолчанию `1`) |
| `status` | string | нет | Статус: `pending`, `confirmed`, `paid`, `delivered`, `cancelled` (по умолчанию `pending`) |
| `notes` | string | нет | Примечания |
| `is_active` | boolean | нет | Активен ли участник (по умолчанию `true`) |

---

#### `GET /api/procurements/participants/{id}/`

Детали участия.

---

#### `PUT /api/procurements/participants/{id}/`

Обновить участие. **Авторизация**: владелец или администратор

**Поля запроса**: те же, что и для `POST /api/procurements/participants/`. При PATCH все поля необязательные.

---

#### `DELETE /api/procurements/participants/{id}/`

Удалить участие. **Авторизация**: владелец или администратор

---

#### `POST /api/procurements/participants/{id}/update_status/`

Изменить статус участника.

**Авторизация**: участник или организатор

**Поля запроса**:

| Поле | Тип | Обязательное | Описание |
|---|---|---|---|
| `status` | string | **да** | Новый статус: `pending`, `confirmed`, `paid`, `delivered`, `cancelled` |

**Пример запроса**:
```json
{
  "status": "confirmed"
}
```

**Ответ**: обновлённый объект участника

---

### Платежи

Базовый путь: `/api/payments/`

#### `GET /api/payments/`

Список платежей.

**Параметры запроса**:

| Параметр | Тип | Описание |
|---|---|---|
| `user_id` | integer | ID пользователя |
| `payment_type` | string | Тип платежа |
| `status` | string | Статус: `pending`, `success`, `failed`, `refunded` |

**Пример**:
```http
GET /api/payments/?user_id=42&status=success
```

**Ответ**:
```json
[
  {
    "id": 500,
    "user_id": 42,
    "amount": "1500.00",
    "status": "success",
    "payment_type": "deposit",
    "provider": "yookassa",
    "external_id": "yoo_123456",
    "order_id": "order_abc",
    "confirmation_url": null,
    "paid_at": "2024-01-15T10:30:00Z",
    "created_at": "2024-01-15T10:25:00Z"
  }
]
```

---

#### `POST /api/payments/`

Создать платёж (пополнение).

**Авторизация**: требуется

**Поля запроса**:

| Поле | Тип | Обязательное | Описание |
|---|---|---|---|
| `user_id` | integer | **да** | ID пользователя |
| `amount` | decimal (12,2) | **да** | Сумма платежа |
| `description` | string | нет | Описание платежа |
| `procurement_id` | integer | нет | ID закупки (если платёж связан с закупкой) |

**Пример запроса**:
```json
{
  "user_id": 42,
  "amount": "1500.00",
  "description": "Пополнение баланса",
  "procurement_id": 101
}
```

**Ответ** (`201 Created`):
```json
{
  "id": 501,
  "user_id": 42,
  "amount": "1500.00",
  "status": "pending",
  "payment_type": "deposit",
  "provider": "yookassa",
  "confirmation_url": "https://yookassa.ru/checkout/payments/...",
  "created_at": "2024-01-15T11:00:00Z"
}
```

---

#### `GET /api/payments/{id}/`

Детали платежа.

---

#### `GET /api/payments/{id}/status/`

Статус платежа.

**Ответ**:
```json
{
  "id": 500,
  "status": "success",
  "status_display": "Успешно",
  "amount": "1500.00",
  "provider": "yookassa",
  "paid_at": "2024-01-15T10:30:00Z",
  "created_at": "2024-01-15T10:25:00Z"
}
```

---

#### `POST /api/payments/{id}/simulate_success/`

Симулировать успешный платёж (только в тестовой среде).

**Авторизация**: владелец или администратор

**Ответ**:
```json
{
  "status": "success",
  "payment": {
    "id": 500,
    "status": "success",
    "paid_at": "2024-01-15T11:05:00Z"
  }
}
```

---

#### `POST /api/payments/webhook/tochka/`

Вебхук от платёжной системы Точка.

**Заголовки**: `X-Signature: <подпись>`

**Тело**: payload от Точка

**Ответ**:
```json
{"status": "ok"}
```

---

#### `POST /api/payments/webhook/yookassa/`

Вебхук от ЮКасса.

**Тело**: payload от YooKassa

**Ответ**:
```json
{"status": "ok"}
```

---

#### `POST /api/payments/webhook/`

Универсальный вебхук (автоопределение провайдера).

---

### Транзакции

Базовый путь: `/api/payments/transactions/`

#### `GET /api/payments/transactions/`

Список транзакций.

**Параметры запроса**:

| Параметр | Тип | Описание |
|---|---|---|
| `user_id` | integer | ID пользователя |
| `transaction_type` | string | Тип: `deposit`, `withdrawal`, `refund`, `commission` |

---

#### `GET /api/payments/transactions/{id}/`

Детали транзакции.

**Ответ**:
```json
{
  "id": 1001,
  "user_id": 42,
  "type": "deposit",
  "amount": "1500.00",
  "balance_after": "1750.00",
  "description": "Пополнение через YooKassa",
  "created_at": "2024-01-15T10:30:00Z"
}
```

---

#### `GET /api/payments/transactions/summary/`

Сводка по транзакциям пользователя.

**Параметры запроса** (обязательный):

| Параметр | Тип | Описание |
|---|---|---|
| `user_id` | integer | ID пользователя |

**Пример**:
```http
GET /api/payments/transactions/summary/?user_id=42
```

**Ответ**:
```json
{
  "user_id": 42,
  "current_balance": "250.00",
  "total_deposited": "5000.00",
  "total_withdrawn": "4500.00",
  "total_refunded": "200.00",
  "transaction_count": 35
}
```

---

### Чат и сообщения

Базовый путь: `/api/chat/messages/`

#### `GET /api/chat/messages/`

Список сообщений чата закупки.

**Параметры запроса**:

| Параметр | Тип | Описание |
|---|---|---|
| `procurement_id` | integer | ID закупки |

**Пример**:
```http
GET /api/chat/messages/?procurement_id=101
```

**Ответ**:
```json
[
  {
    "id": 2001,
    "procurement_id": 101,
    "user_id": 42,
    "text": "Когда ожидать поставку?",
    "message_type": "text",
    "attachment_url": null,
    "is_deleted": false,
    "created_at": "2024-01-20T14:00:00Z"
  }
]
```

---

#### `POST /api/chat/messages/`

Отправить сообщение.

**Авторизация**: требуется

**Поля запроса**:

| Поле | Тип | Обязательное | Описание |
|---|---|---|---|
| `procurement_id` | integer | **да** | ID закупки |
| `user_id` | integer | **да** | ID отправителя |
| `text` | string | **да** | Текст сообщения |
| `message_type` | string | нет | Тип сообщения: `text`, `image`, `file` (по умолчанию `text`) |
| `attachment_url` | string (URL) | нет | Ссылка на вложение |

**Пример запроса**:
```json
{
  "procurement_id": 101,
  "user_id": 42,
  "text": "Когда ожидать поставку?",
  "message_type": "text",
  "attachment_url": null
}
```

**Ответ** (`201 Created`): объект сообщения

---

#### `GET /api/chat/messages/{id}/`

Детали сообщения.

---

#### `PUT /api/chat/messages/{id}/`

Редактировать сообщение. **Авторизация**: владелец или администратор

---

#### `DELETE /api/chat/messages/{id}/`

Удалить сообщение. **Авторизация**: владелец или администратор

---

#### `POST /api/chat/messages/mark_read/`

Отметить сообщения как прочитанные.

**Авторизация**: требуется

**Поля запроса**:

| Поле | Тип | Обязательное | Описание |
|---|---|---|---|
| `user_id` | integer | **да** | ID пользователя |
| `procurement_id` | integer | **да** | ID закупки |
| `message_id` | integer | нет | ID конкретного сообщения; если не указан — отмечаются все сообщения закупки |

**Пример запроса**:
```json
{
  "user_id": 42,
  "procurement_id": 101,
  "message_id": 2001
}
```

**Ответ**:
```json
{"message": "Marked as read"}
```

---

#### `GET /api/chat/messages/unread_count/`

Количество непрочитанных сообщений.

**Авторизация**: требуется

**Параметры запроса**:

| Параметр | Тип | Описание |
|---|---|---|
| `user_id` | integer | ID пользователя (обязательно) |
| `procurement_id` | integer | ID закупки (необязательно) |

**Ответ**:
```json
{
  "procurement_id": 101,
  "unread_count": 5
}
```

---

### Уведомления

Базовый путь: `/api/chat/notifications/`

#### `GET /api/chat/notifications/`

Список уведомлений.

**Параметры запроса**:

| Параметр | Тип | Описание |
|---|---|---|
| `user_id` | integer | ID пользователя |
| `unread_only` | boolean | Только непрочитанные |

---

#### `POST /api/chat/notifications/`

Создать уведомление. **Авторизация**: требуется

**Поля запроса**:

| Поле | Тип | Обязательное | Описание |
|---|---|---|---|
| `user_id` | integer | **да** | ID получателя |
| `notification_type` | string | **да** | Тип уведомления (например, `procurement_update`, `system`) |
| `title` | string | **да** | Заголовок уведомления |
| `message` | string | **да** | Текст уведомления |
| `procurement_id` | integer | нет | ID связанной закупки |

---

#### `GET /api/chat/notifications/{id}/`

Детали уведомления.

---

#### `PUT /api/chat/notifications/{id}/`

Обновить уведомление. **Авторизация**: владелец или администратор

**Поля запроса**: те же, что и для `POST /api/chat/notifications/`. При PATCH все поля необязательные.

---

#### `DELETE /api/chat/notifications/{id}/`

Удалить уведомление. **Авторизация**: владелец или администратор

---

#### `POST /api/chat/notifications/{id}/mark_read/`

Отметить уведомление как прочитанное.

**Авторизация**: владелец

**Ответ**: обновлённое уведомление

---

#### `POST /api/chat/notifications/mark_all_read/`

Отметить все уведомления как прочитанные.

**Авторизация**: требуется

**Тело запроса**:
```json
{
  "user_id": 42
}
```

**Ответ**:
```json
{"message": "Marked 7 notifications as read"}
```

---

#### `POST /api/chat/notifications/send/`

Отправить уведомление пользователю.

**Авторизация**: требуется

**Тело запроса**:
```json
{
  "user_id": 42,
  "notification_type": "procurement_update",
  "title": "Закупка обновлена",
  "message": "Организатор изменил условия закупки #101",
  "procurement_id": 101
}
```

**Ответ** (`201 Created`): объект уведомления

---

### ML — Модели и предсказания

Базовый путь: `/api/ml/`

#### `GET /api/ml/models/`

Список ML-моделей.

**Авторизация**: публичный

---

#### `GET /api/ml/models/{id}/`

Детали ML-модели.

---

#### `GET /api/ml/models/status/`

Статус ML-подсистемы.

**Ответ**:
```json
{
  "plexe_available": true,
  "message": "ML service is running"
}
```

---

#### `POST /api/ml/models/train/`

Обучить модель.

**Авторизация**: требуется

**Поля запроса**:

| Поле | Тип | Обязательное | Описание |
|---|---|---|---|
| `model_type` | string | **да** | Тип модели: `success_prediction`, `demand_forecast` |
| `max_iterations` | integer | нет | Максимальное число итераций обучения |
| `work_dir` | string | нет | Рабочая директория для сохранения модели |

**Пример запроса**:
```json
{
  "model_type": "success_prediction",
  "max_iterations": 100,
  "work_dir": "/tmp/ml_models"
}
```

**Ответ** (`201 Created`):
```json
{
  "id": 5,
  "model_type": "success_prediction",
  "status": "trained",
  "accuracy": 0.87,
  "trained_at": "2024-01-20T15:00:00Z"
}
```

При недоступности ML-сервиса: `503 Service Unavailable`

---

#### `GET /api/ml/predictions/`

Список предсказаний.

**Параметры запроса**:

| Параметр | Тип | Описание |
|---|---|---|
| `procurement` | integer | ID закупки |

---

#### `GET /api/ml/predictions/{id}/`

Детали предсказания.

---

#### `POST /api/ml/predictions/predict/`

Запустить предсказание для закупки.

**Авторизация**: требуется

**Поля запроса**:

| Поле | Тип | Обязательное | Описание |
|---|---|---|---|
| `procurement_id` | integer | **да** | ID закупки для предсказания |
| `prediction_type` | string | нет | Тип предсказания: `success_prediction`, `demand_forecast` |

**Пример запроса**:
```json
{
  "procurement_id": 101,
  "prediction_type": "success_prediction"
}
```

**Ответ** (`201 Created`):
```json
{
  "id": 20,
  "procurement_id": 101,
  "prediction_type": "success_prediction",
  "predicted_value": 0.78,
  "confidence": 0.85,
  "created_at": "2024-01-20T16:00:00Z"
}
```

---

### Административный API

Базовый путь: `/api/admin/`

**Авторизация**: все эндпоинты требуют роли `IsAdminUser`

---

#### `POST /api/admin/auth/`

Авторизация администратора.

**Поля запроса**:

| Поле | Тип | Обязательное | Описание |
|---|---|---|---|
| `username` | string | **да** | Имя пользователя администратора |
| `password` | string | **да** | Пароль |

**Пример запроса**:
```json
{
  "username": "admin",
  "password": "securepassword"
}
```

**Ответ**: данные пользователя + токены

---

#### `GET /api/admin/auth/`

Получить текущего авторизованного администратора.

---

#### `DELETE /api/admin/auth/`

Выйти из системы.

**Ответ**:
```json
{"detail": "Logged out"}
```

---

#### `GET /api/admin/dashboard/`

Сводная статистика для дашборда.

**Ответ**:
```json
{
  "total_users": 1500,
  "active_procurements": 45,
  "total_payments_amount": "3500000.00",
  "total_messages": 8720
}
```

---

#### `GET /api/admin/analytics/`

Аналитика за период.

**Параметры запроса**:

| Параметр | Тип | Описание |
|---|---|---|
| `date_from` | date | Начало периода (`YYYY-MM-DD`) |
| `date_to` | date | Конец периода (`YYYY-MM-DD`) |
| `period` | string | Группировка: `day`, `week`, `month` |

**Пример**:
```http
GET /api/admin/analytics/?date_from=2024-01-01&date_to=2024-01-31&period=week
```

**Ответ**:
```json
{
  "time_series": [
    {"date": "2024-01-01", "new_users": 25, "new_procurements": 8, "payments_amount": "125000.00"}
  ],
  "top_categories": [{"id": 5, "name": "Одежда", "count": 120}],
  "top_organizers": [{"id": 42, "username": "best_org", "count": 15}],
  "conversion_funnel": {
    "registered": 500,
    "joined_procurement": 350,
    "paid": 280
  }
}
```

---

#### `GET /api/admin/users/`

Список пользователей с расширенными фильтрами.

**Параметры запроса**:

| Параметр | Тип | Описание |
|---|---|---|
| `role` | string | Роль |
| `platform` | string | Платформа |
| `is_active` | boolean | Активен |
| `is_verified` | boolean | Верифицирован |
| `search` | string | Поиск |

---

#### `POST /api/admin/users/{id}/toggle_active/`

Включить/выключить пользователя.

**Ответ**:
```json
{"is_active": false}
```

---

#### `POST /api/admin/users/{id}/toggle_verified/`

Верифицировать/снять верификацию.

**Ответ**:
```json
{"is_verified": true}
```

---

#### `POST /api/admin/users/{id}/update_balance/`

Изменить баланс пользователя вручную.

**Поля запроса**:

| Поле | Тип | Обязательное | Описание |
|---|---|---|---|
| `amount` | decimal | **да** | Сумма изменения баланса (положительная — пополнение, отрицательная — списание) |
| `description` | string | нет | Причина изменения баланса |

**Пример запроса**:
```json
{
  "amount": "500.00",
  "description": "Бонус за активность"
}
```

**Ответ**:
```json
{
  "old_balance": "250.00",
  "new_balance": "750.00",
  "amount": "500.00"
}
```

---

#### `POST /api/admin/users/bulk_action/`

Массовые действия над пользователями.

**Поля запроса**:

| Поле | Тип | Обязательное | Описание |
|---|---|---|---|
| `ids` | array of integer | **да** | Список ID пользователей |
| `action` | string | **да** | Действие: `activate`, `deactivate`, `verify`, `unverify` |

**Пример запроса**:
```json
{
  "ids": [10, 15, 22, 30],
  "action": "verify"
}
```

**Ответ**:
```json
{"affected": 4}
```

---

#### `POST /api/admin/procurements/{id}/update_status/`

Изменить статус закупки (от имени администратора).

**Поля запроса**:

| Поле | Тип | Обязательное | Описание |
|---|---|---|---|
| `status` | string | **да** | Новый статус: `draft`, `active`, `stopped`, `payment`, `completed`, `cancelled` |

**Пример запроса**:
```json
{
  "status": "active"
}
```

**Ответ**:
```json
{
  "old_status": "draft",
  "new_status": "open"
}
```

---

#### `POST /api/admin/procurements/{id}/toggle_featured/`

Включить/выключить «Рекомендовано».

**Ответ**:
```json
{"is_featured": true}
```

---

#### `POST /api/admin/procurements/bulk_action/`

Массовые действия над закупками.

**Поля запроса**:

| Поле | Тип | Обязательное | Описание |
|---|---|---|---|
| `ids` | array of integer | **да** | Список ID закупок |
| `action` | string | **да** | Действие: `feature`, `unfeature`, или любой статус (`draft`, `active`, `stopped`, `payment`, `completed`, `cancelled`) |

**Пример запроса**:
```json
{
  "ids": [101, 102, 103],
  "action": "feature"
}
```

**Ответ**:
```json
{"affected": 3}
```

---

#### `GET /api/admin/payments/summary/`

Сводка по платежам.

**Ответ**:
```json
{
  "by_status": {
    "pending": {"count": 5, "amount": "7500.00"},
    "success": {"count": 120, "amount": "350000.00"},
    "failed": {"count": 8, "amount": "12000.00"}
  },
  "by_type": {
    "deposit": {"count": 100, "amount": "300000.00"},
    "refund": {"count": 28, "amount": "62000.00"}
  }
}
```

---

#### `POST /api/admin/messages/{id}/toggle_delete/`

Удалить/восстановить сообщение.

**Ответ**:
```json
{"is_deleted": true}
```

---

#### `POST /api/admin/chat/admin_message/`

Отправить сообщение пользователю от имени администратора.

**Поля запроса**:

| Поле | Тип | Обязательное | Описание |
|---|---|---|---|
| `user_id` | integer | **да** | ID получателя |
| `text` | string | **да** | Текст сообщения |

**Пример запроса**:
```json
{
  "user_id": 42,
  "text": "Ваша закупка проверена и одобрена."
}
```

**Ответ**:
```json
{
  "id": 3001,
  "user_id": 42,
  "text": "Ваша закупка проверена и одобрена."
}
```

---

#### `POST /api/admin/notifications/send_bulk/`

Массовая рассылка уведомлений.

**Поля запроса**:

| Поле | Тип | Обязательное | Описание |
|---|---|---|---|
| `user_ids` | array of integer | **да** | Список ID получателей |
| `notification_type` | string | **да** | Тип уведомления: `system`, `procurement_update`, и др. |
| `title` | string | **да** | Заголовок уведомления |
| `message` | string | **да** | Текст уведомления |

**Пример запроса**:
```json
{
  "user_ids": [10, 15, 22, 30, 42],
  "notification_type": "system",
  "title": "Технические работы",
  "message": "Плановые технические работы 25 января с 02:00 до 04:00 МСК."
}
```

**Ответ**:
```json
{"sent": 5}
```

---

## Микросервисы

### Auth Service (порт 4001)

Базовый URL: `http://auth-service:4001` (или через Gateway: `/api/v1/auth/...`)

Технология: NestJS

Аутентификация построена на основе **OTP (одноразовый код)**, отправляемого на email пользователя. Пароли не используются.

---

#### `POST /register`

**Шаг 1**: Начало регистрации — проверяет уникальность телефона и email, отправляет OTP-код на email.

**Поля запроса**:

| Поле | Тип | Обязательное | Описание |
|---|---|---|---|
| `phone` | string | **да** | Номер телефона (формат: `+79001234567`) |
| `email` | string (email) | **да** | Email пользователя |
| `firstName` | string | нет | Имя |
| `lastName` | string | нет | Фамилия |
| `role` | string | нет | Роль: `buyer`, `organizer`, `supplier` |

**Пример запроса**:
```json
{
  "phone": "+79001234567",
  "email": "user@example.com",
  "firstName": "Иван",
  "lastName": "Петров",
  "role": "buyer"
}
```

**Ответ** (`200 OK`):
```json
{
  "success": true,
  "data": {
    "message": "OTP sent to email"
  }
}
```

---

#### `POST /register/confirm`

**Шаг 2**: Подтверждение регистрации — проверяет OTP и возвращает JWT-токены.

**Поля запроса**:

| Поле | Тип | Обязательное | Описание |
|---|---|---|---|
| `phone` | string | **да** | Номер телефона |
| `otp` | string (4–8 символов) | **да** | OTP-код из письма |

**Пример запроса**:
```json
{
  "phone": "+79001234567",
  "otp": "123456"
}
```

**Ответ** (`201 Created`):
```json
{
  "success": true,
  "data": {
    "accessToken": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
    "refreshToken": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
    "expiresIn": 3600
  }
}
```

---

#### `POST /login`

**Шаг 1**: Начало входа по номеру телефона — отправляет OTP-код на зарегистрированный email пользователя.

**Поля запроса**:

| Поле | Тип | Обязательное | Описание |
|---|---|---|---|
| `phone` | string | **да** | Номер телефона пользователя |

**Пример запроса**:
```json
{
  "phone": "+79001234567"
}
```

**Ответ** (`200 OK`):
```json
{
  "success": true,
  "data": {
    "message": "OTP sent to email"
  }
}
```

---

#### `POST /login/confirm`

**Шаг 2**: Подтверждение входа — проверяет OTP и возвращает JWT-токены (или `tempToken` при включённой 2FA).

**Поля запроса**:

| Поле | Тип | Обязательное | Описание |
|---|---|---|---|
| `phone` | string | **да** | Номер телефона |
| `otp` | string (4–8 символов) | **да** | OTP-код из письма |

**Пример запроса**:
```json
{
  "phone": "+79001234567",
  "otp": "654321"
}
```

**Ответ** (`200 OK`):
```json
{
  "success": true,
  "data": {
    "accessToken": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
    "refreshToken": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
    "expiresIn": 3600
  }
}
```

Если у пользователя включена 2FA — возвращается `tempToken` вместо основных токенов:
```json
{
  "success": true,
  "data": {
    "tempToken": "temp-jwt-token...",
    "requires2FA": true
  }
}

---

#### `POST /refresh`

Обновить access-токен.

**Тело запроса**:
```json
{
  "refreshToken": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
}
```

**Ответ** (`200 OK`): новая пара токенов

---

#### `POST /logout`

Выйти из системы.

**Заголовки**: `Authorization: Bearer <token>`

**Ответ**:
```json
{
  "success": true,
  "message": "Logged out successfully"
}
```

---

#### `GET /validate`

Валидировать JWT-токен.

**Заголовки**: `Authorization: Bearer <token>`

**Ответ**:
```json
{
  "success": true,
  "data": {
    "userId": "uuid-...",
    "email": "user@example.com",
    "role": "buyer"
  }
}
```

---

#### `GET /health`

Проверка доступности сервиса.

**Ответ**:
```json
{"status": "ok", "service": "auth-service"}
```

---

#### `POST /2fa/enable`

Включить двухфакторную аутентификацию.

**Заголовки**: `Authorization: Bearer <token>`

**Ответ**:
```json
{
  "success": true,
  "data": {
    "qrCode": "data:image/png;base64,...",
    "secret": "JBSWY3DPEHPK3PXP"
  }
}
```

---

#### `POST /2fa/verify`

Подтвердить включение 2FA.

**Заголовки**: `Authorization: Bearer <token>`

**Тело запроса**:
```json
{
  "code": "123456"
}
```

**Ответ**:
```json
{
  "success": true,
  "message": "Two-factor authentication enabled successfully"
}
```

---

#### `POST /2fa/login`

Войти с 2FA-кодом (используется если при `POST /login/confirm` был возвращён `tempToken`).

**Поля запроса**:

| Поле | Тип | Обязательное | Описание |
|---|---|---|---|
| `tempToken` | string | **да** | Временный токен из ответа `POST /login/confirm` |
| `code` | string | **да** | Код из приложения 2FA или резервный код |

**Пример запроса**:
```json
{
  "tempToken": "temp-jwt-token-from-login-confirm",
  "code": "123456"
}
```

**Ответ** (`200 OK`): полная пара токенов (как при `/login/confirm` без 2FA)

---

#### `POST /2fa/disable`

Отключить 2FA.

**Заголовки**: `Authorization: Bearer <token>`

**Тело запроса**:
```json
{
  "code": "123456"
}
```

---

#### `POST /2fa/backup-codes`

Сгенерировать резервные коды 2FA.

**Заголовки**: `Authorization: Bearer <token>`

**Тело запроса**:
```json
{
  "code": "123456"
}
```

**Ответ**:
```json
{
  "success": true,
  "data": {
    "backupCodes": ["abc123", "def456", "ghi789", ...]
  }
}
```

---

### Purchase Service (порт 4002)

Базовый URL: `http://purchase-service:4002` (или через Gateway: `/api/v1/purchases/...` и `/api/v1/voting/...`)

Технология: NestJS

---

#### `POST /purchases`

Создать закупку (Purchase).

**Заголовки**: `x-user-id: <userId>`

**Поля запроса**:

| Поле | Тип | Обязательное | Описание |
|---|---|---|---|
| `title` | string | **да** | Название закупки |
| `description` | string | нет | Описание |
| `minParticipants` | integer | нет | Минимальное число участников |
| `maxParticipants` | integer | нет | Максимальное число участников |
| `targetAmount` | number | нет | Целевая сумма |
| `currency` | string | нет | Валюта (например, `RUB`) |
| `category` | string | нет | Категория (например, `electronics`) |
| `commissionPercent` | number | нет | Комиссия организатора в % |
| `escrowThreshold` | number | нет | Порог эскроу |
| `deadlineAt` | datetime | нет | Дедлайн (ISO 8601) |

**Пример запроса**:
```json
{
  "title": "Совместная закупка ноутбуков",
  "description": "MacBook Pro 14 дюймов",
  "minParticipants": 5,
  "maxParticipants": 20,
  "targetAmount": 500000,
  "currency": "RUB",
  "category": "electronics",
  "commissionPercent": 3.5,
  "escrowThreshold": 300000,
  "deadlineAt": "2024-03-01T00:00:00Z"
}
```

**Ответ** (`201 Created`):
```json
{
  "success": true,
  "data": {
    "id": "uuid-...",
    "title": "Совместная закупка ноутбуков",
    "status": "DRAFT",
    "organizerId": "uuid-...",
    "createdAt": "2024-01-15T10:00:00Z"
  }
}
```

---

#### `GET /purchases`

Список закупок (с пагинацией).

**Параметры запроса**:

| Параметр | Тип | По умолчанию | Описание |
|---|---|---|---|
| `page` | integer | 1 | Страница |
| `limit` | integer | 20 | Количество (макс. 100) |

**Ответ**:
```json
{
  "success": true,
  "data": [...],
  "total": 150,
  "page": 1
}
```

---

#### `GET /purchases/{id}`

Детали закупки.

**Ответ**:
```json
{
  "success": true,
  "data": {
    "id": "uuid-...",
    "title": "Совместная закупка ноутбуков",
    "status": "OPEN",
    "organizerId": "uuid-...",
    "targetAmount": 500000,
    "currentAmount": 125000,
    "participantsCount": 5
  }
}
```

---

#### `PUT /purchases/{id}`

Обновить закупку.

**Заголовки**: `x-user-id: <userId>`

**Тело запроса**: частичный объект `CreatePurchaseDto`

---

#### `DELETE /purchases/{id}`

Удалить/отменить закупку.

**Заголовки**: `x-user-id: <userId>`

---

#### `GET /purchases/{id}/editors`

Список редакторов закупки.

---

#### `POST /purchases/{id}/editors`

Добавить редактора.

**Заголовки**: `x-user-id: <userId>`

**Тело запроса**:
```json
{
  "user_id": "uuid-editor"
}
```

---

#### `DELETE /purchases/{id}/editors/{editorId}`

Удалить редактора.

**Заголовки**: `x-user-id: <userId>`

---

#### `POST /purchases/{id}/invite`

Пригласить пользователя участвовать в закупке. Любой участник или организатор может пригласить другого пользователя. Приглашённый появится как ожидающий участник до подтверждения.

**Заголовки**: `x-user-id: <userId>`

**Поля запроса**:

| Поле | Тип | Обязательное | Описание |
|---|---|---|---|
| `user_id` | string (uuid) | **да** | UUID приглашаемого пользователя |

**Пример запроса**:
```json
{
  "user_id": "uuid-invited-user"
}
```

**Ответ** (`200 OK`):
```json
{
  "success": true,
  "data": {
    "purchaseId": "uuid-purchase",
    "invitedUserId": "uuid-invited-user",
    "status": "PENDING"
  }
}
```

---

#### `POST /voting/sessions`

Создать сессию голосования.

**Заголовки**: `x-user-id: <userId>`

**Поля запроса**:

| Поле | Тип | Обязательное | Описание |
|---|---|---|---|
| `purchaseId` | string (uuid) | **да** | ID закупки |
| `closesAt` | datetime | нет | Время закрытия голосования (ISO 8601) |
| `allowAddCandidates` | boolean | нет | Разрешить добавлять кандидатов |
| `allowChangeVote` | boolean | нет | Разрешить менять голос |
| `minVotesToClose` | integer | нет | Минимальное число голосов для закрытия |
| `votingDuration` | integer | нет | Длительность голосования в часах |

**Пример запроса**:
```json
{
  "purchaseId": "uuid-...",
  "closesAt": "2024-02-01T00:00:00Z",
  "allowAddCandidates": true,
  "allowChangeVote": false,
  "minVotesToClose": 10,
  "votingDuration": 72
}
```

**Ответ** (`201 Created`):
```json
{
  "success": true,
  "data": {
    "id": "uuid-session",
    "purchaseId": "uuid-...",
    "status": "OPEN",
    "closesAt": "2024-02-01T00:00:00Z"
  }
}
```

---

#### `POST /voting/sessions/{sessionId}/candidates`

Добавить кандидата-поставщика.

**Заголовки**: `x-user-id: <userId>`

**Поля запроса**:

| Поле | Тип | Обязательное | Описание |
|---|---|---|---|
| `supplierName` | string | **да** | Название поставщика |
| `description` | string | нет | Описание поставщика |
| `pricePerUnit` | number | нет | Цена за единицу товара |
| `unit` | string | нет | Единица измерения |
| `supplierUrl` | string (URL) | нет | Ссылка на поставщика |

**Пример запроса**:
```json
{
  "supplierName": "ООО Поставщик",
  "description": "Надёжный поставщик электроники",
  "pricePerUnit": 75000,
  "unit": "шт",
  "supplierUrl": "https://supplier.example.com"
}
```

**Ответ** (`201 Created`): объект кандидата

---

#### `POST /voting/sessions/{sessionId}/votes`

Проголосовать.

**Заголовки**: `x-user-id: <userId>`

**Поля запроса**:

| Поле | Тип | Обязательное | Описание |
|---|---|---|---|
| `candidateId` | string (uuid) | **да** | ID кандидата-поставщика |
| `comment` | string | нет | Комментарий к голосу |

**Пример запроса**:
```json
{
  "candidateId": "uuid-candidate",
  "comment": "Лучший по соотношению цена/качество"
}
```

**Ответ** (`200 OK`): объект голоса

---

#### `GET /voting/sessions/{sessionId}/results`

Результаты голосования.

**Заголовки**: `x-user-id: <userId>` (необязательно)

**Ответ**:
```json
{
  "success": true,
  "data": {
    "sessionId": "uuid-session",
    "totalVotes": 12,
    "candidates": [
      {
        "id": "uuid-candidate",
        "supplierName": "ООО Поставщик",
        "votes": 8,
        "percent": 66.7
      }
    ]
  }
}
```

---

#### `PATCH /voting/sessions/{sessionId}/close`

Закрыть сессию голосования досрочно.

**Заголовки**: `x-user-id: <userId>`

**Ответ** (`200 OK`):
```json
{
  "success": true,
  "data": {
    "id": "uuid-session",
    "status": "CLOSED",
    "closedAt": "2024-02-01T12:00:00Z"
  }
}
```

---

#### `POST /voting/sessions/{sessionId}/resolve-tie`

Разрешить ничью в голосовании — выбрать победителя вручную.

**Заголовки**: `x-user-id: <userId>`

**Поля запроса**:

| Поле | Тип | Обязательное | Описание |
|---|---|---|---|
| `candidateId` | string (uuid) | **да** | ID кандидата-победителя |

**Пример запроса**:
```json
{
  "candidateId": "uuid-winning-candidate"
}
```

**Ответ** (`200 OK`):
```json
{
  "success": true,
  "data": {
    "id": "uuid-session",
    "status": "CLOSED",
    "winnerId": "uuid-winning-candidate"
  }
}
```

---

#### `GET /purchases/health`

Проверка доступности сервиса.

**Ответ**:
```json
{"status": "ok", "service": "purchase-service"}
```

---

### Payment Service (порт 4003)

Базовый URL: `http://payment-service:4003` (или через Gateway: `/payment/...`)

Технология: Go

---

#### `GET /health`

```json
{"status": "ok", "service": "payment-service"}
```

---

#### `GET /wallet`

Получить кошелёк пользователя.

**Заголовки**: `X-User-ID: <userId>`

**Ответ**:
```json
{
  "id": "uuid-wallet",
  "userId": "uuid-user",
  "balance": 25000,
  "heldAmount": 5000,
  "availableBalance": 20000,
  "currency": "RUB"
}
```

---

#### `POST /wallet/topup`

Пополнить кошелёк.

**Поля запроса**:

| Поле | Тип | Обязательное | Описание |
|---|---|---|---|
| `user_id` | string (uuid) | **да** | ID пользователя |
| `amount` | number | **да** | Сумма пополнения |
| `idempotency_key` | string | **да** | Ключ идемпотентности |

**Пример запроса**:
```json
{
  "user_id": "uuid-user",
  "amount": 10000,
  "idempotency_key": "topup-20240115-001"
}
```

**Ответ**: объект транзакции

---

#### `POST /wallet/hold`

Заморозить средства для участия в закупке.

**Поля запроса**:

| Поле | Тип | Обязательное | Описание |
|---|---|---|---|
| `user_id` | string (uuid) | **да** | ID пользователя |
| `purchase_id` | string (uuid) | **да** | ID закупки |
| `amount` | number | **да** | Сумма заморозки |
| `idempotency_key` | string | **да** | Ключ идемпотентности |

**Пример запроса**:
```json
{
  "user_id": "uuid-user",
  "purchase_id": "uuid-purchase",
  "amount": 5000,
  "idempotency_key": "hold-20240115-001"
}
```

**Ответ**: объект транзакции (тип `HOLD`)

---

#### `POST /wallet/commit`

Подтвердить списание замороженных средств.

**Поля запроса**:

| Поле | Тип | Обязательное | Описание |
|---|---|---|---|
| `user_id` | string (uuid) | **да** | ID пользователя |
| `hold_tx_id` | string (uuid) | **да** | ID транзакции заморозки |

**Пример запроса**:
```json
{
  "user_id": "uuid-user",
  "hold_tx_id": "uuid-hold-transaction"
}
```

---

#### `POST /wallet/release`

Разморозить средства (отмена участия).

**Поля запроса**:

| Поле | Тип | Обязательное | Описание |
|---|---|---|---|
| `user_id` | string (uuid) | **да** | ID пользователя |
| `hold_tx_id` | string (uuid) | **да** | ID транзакции заморозки |

**Пример запроса**:
```json
{
  "user_id": "uuid-user",
  "hold_tx_id": "uuid-hold-transaction"
}
```

---

#### `POST /escrow`

Создать счёт эскроу для закупки.

**Поля запроса**:

| Поле | Тип | Обязательное | Описание |
|---|---|---|---|
| `purchase_id` | string (uuid) | **да** | ID закупки |
| `threshold` | number | нет | Порог суммы для автоматического разблокирования |

**Пример запроса**:
```json
{
  "purchase_id": "uuid-purchase",
  "threshold": 100000
}
```

**Ответ**:
```json
{
  "id": "uuid-escrow",
  "purchaseId": "uuid-purchase",
  "status": "PENDING",
  "balance": 0,
  "threshold": 100000
}
```

---

#### `GET /escrow/{purchaseId}`

Данные эскроу-счёта.

---

#### `POST /escrow/{purchaseId}/deposit`

Внести средства в эскроу.

**Поля запроса**:

| Поле | Тип | Обязательное | Описание |
|---|---|---|---|
| `user_id` | string (uuid) | **да** | ID пользователя |
| `amount` | number | **да** | Сумма взноса |
| `idempotency_key` | string | **да** | Ключ идемпотентности |

**Пример запроса**:
```json
{
  "user_id": "uuid-user",
  "amount": 25000,
  "idempotency_key": "escrow-deposit-001"
}
```

---

#### `POST /escrow/{purchaseId}/confirm`

Подтвердить завершение закупки (получение товара).

**Поля запроса**:

| Поле | Тип | Обязательное | Описание |
|---|---|---|---|
| `user_id` | string (uuid) | **да** | ID пользователя, подтверждающего получение |

**Пример запроса**:
```json
{
  "user_id": "uuid-user"
}
```

---

#### `POST /escrow/{purchaseId}/release`

Выплатить средства поставщику.

**Поля запроса**:

| Поле | Тип | Обязательное | Описание |
|---|---|---|---|
| `recipient_id` | string (uuid) | **да** | ID получателя (поставщика) |
| `amount` | number | **да** | Сумма выплаты |

**Пример запроса**:
```json
{
  "recipient_id": "uuid-supplier",
  "amount": 95000
}
```

---

#### `POST /escrow/{purchaseId}/dispute`

Открыть спор по эскроу.

**Поля запроса**:

| Поле | Тип | Обязательное | Описание |
|---|---|---|---|
| `user_id` | string (uuid) | **да** | ID пользователя, открывающего спор |
| `reason` | string | **да** | Причина спора |

**Пример запроса**:
```json
{
  "user_id": "uuid-user",
  "reason": "Товар не соответствует описанию"
}
```

---

#### `POST /commission/hold`

Зарезервировать комиссию.

**Поля запроса**:

| Поле | Тип | Обязательное | Описание |
|---|---|---|---|
| `purchase_id` | string (uuid) | **да** | ID закупки |
| `organizer_wallet_id` | string (uuid) | **да** | ID кошелька организатора |
| `amount` | number | **да** | Общая сумма закупки |
| `percent` | number | **да** | Процент комиссии |

**Пример запроса**:
```json
{
  "purchase_id": "uuid-purchase",
  "organizer_wallet_id": "uuid-wallet",
  "amount": 100000,
  "percent": 3.5
}
```

---

#### `POST /commission/commit`

Подтвердить комиссию.

**Поля запроса**:

| Поле | Тип | Обязательное | Описание |
|---|---|---|---|
| `commission_hold_id` | string (uuid) | **да** | ID резервирования комиссии |

**Пример запроса**:
```json
{
  "commission_hold_id": "uuid-hold"
}
```

---

#### `POST /commission/release`

Вернуть комиссию (при отмене).

**Поля запроса**:

| Поле | Тип | Обязательное | Описание |
|---|---|---|---|
| `commission_hold_id` | string (uuid) | **да** | ID резервирования комиссии |

**Пример запроса**:
```json
{
  "commission_hold_id": "uuid-hold"
}
```

---

#### `GET /commission/{purchaseId}`

Данные о комиссии.

---

#### `POST /webhooks/stripe`

Вебхук от Stripe.

**Ответ**:
```json
{"status": "ok"}
```

---

#### `POST /webhooks/yookassa`

Вебхук от YooKassa.

**Ответ**:
```json
{"status": "ok"}
```

---

### Reputation Service (порт 4008)

Базовый URL: `http://reputation-service:4008` (или через Gateway: `/api/v1/reputation/...`, `/api/v1/reviews/...`, `/api/v1/complaints/...`)

Технология: NestJS

---

#### `POST /reviews`

Оставить отзыв.

**Поля запроса**:

| Поле | Тип | Обязательное | Описание |
|---|---|---|---|
| `reviewerId` | string (uuid) | **да** | ID автора отзыва |
| `targetId` | string (uuid) | **да** | ID оцениваемого пользователя |
| `purchaseId` | string (uuid) | **да** | ID закупки |
| `role` | string | **да** | Роль рецензента: `buyer`, `organizer`, `supplier` |
| `rating` | integer (1–5) | **да** | Общая оценка |
| `expiresAt` | datetime | **да** | Время истечения отзыва (ISO 8601) |
| `categories` | object | нет | Оценки по категориям: `reliability`, `speed`, `quality`, `timeliness` (каждая 1–5) |
| `comment` | string | нет | Комментарий |

**Пример запроса**:
```json
{
  "reviewerId": "uuid-reviewer",
  "targetId": "uuid-target",
  "purchaseId": "uuid-purchase",
  "role": "buyer",
  "rating": 5,
  "categories": {
    "reliability": 5,
    "speed": 4,
    "quality": 5,
    "timeliness": 4
  },
  "comment": "Отличный организатор, всё чётко и в срок!",
  "expiresAt": "2025-01-15T00:00:00Z"
}
```

**Ответ** (`201 Created`):
```json
{
  "success": true,
  "data": {
    "id": "uuid-review",
    "reviewerId": "uuid-reviewer",
    "targetId": "uuid-target",
    "rating": 5,
    "createdAt": "2024-01-15T12:00:00Z"
  }
}
```

---

#### `GET /reviews/user/{userId}`

Отзывы о пользователе.

**Параметры запроса**:

| Параметр | Тип | Описание |
|---|---|---|
| `role` | string | Роль (`buyer`, `organizer`) |
| `limit` | integer | Количество записей |
| `offset` | integer | Смещение |

**Ответ**:
```json
{
  "success": true,
  "data": {
    "reviews": [...],
    "total": 25,
    "averageRating": 4.7
  }
}
```

---

#### `GET /reputation/{userId}`

Репутация пользователя.

**Ответ**:
```json
{
  "success": true,
  "data": {
    "userId": "uuid-user",
    "score": 4.7,
    "totalReviews": 25,
    "limits": {
      "maxPurchaseAmount": 500000,
      "canBeOrganizer": true
    }
  }
}
```

---

#### `GET /reputation/{userId}/ratings-by-role`

Средний рейтинг пользователя в разбивке по ролям (покупатель, организатор, поставщик). Позволяет отображать отдельные звёздные рейтинги для каждого контекста, в котором работает пользователь.

**Ответ**:
```json
{
  "success": true,
  "data": {
    "buyer": {
      "averageRating": 4.8,
      "totalReviews": 12
    },
    "organizer": {
      "averageRating": 4.5,
      "totalReviews": 8
    },
    "supplier": {
      "averageRating": null,
      "totalReviews": 0
    }
  }
}
```

---

#### `POST /complaints`

Подать жалобу.

**Поля запроса**:

| Поле | Тип | Обязательное | Описание |
|---|---|---|---|
| `reporterId` | string (uuid) | **да** | ID пользователя, подающего жалобу |
| `targetId` | string (uuid) | **да** | ID пользователя, на которого жалоба |
| `type` | string | **да** | Тип жалобы: `fraud`, и др. |
| `description` | string (мин. 10 символов) | **да** | Описание жалобы |
| `purchaseId` | string (uuid) | нет | ID связанной закупки |
| `evidenceUrls` | array of string (URL) | нет | Ссылки на доказательства |

**Пример запроса**:
```json
{
  "reporterId": "uuid-reporter",
  "targetId": "uuid-target",
  "purchaseId": "uuid-purchase",
  "type": "fraud",
  "description": "Организатор собрал деньги и перестал выходить на связь",
  "evidenceUrls": ["https://example.com/screenshot1.png"]
}
```

**Ответ** (`201 Created`): объект жалобы

---

#### `GET /complaints`

Список жалоб (для администраторов).

**Параметры запроса**:

| Параметр | Тип | Описание |
|---|---|---|
| `status` | string | Статус: `PENDING`, `RESOLVED`, `REJECTED` |
| `limit` | integer | Количество |
| `offset` | integer | Смещение |

---

#### `GET /complaints/user/{userId}`

Жалобы пользователя.

**Параметры запроса**: `limit`, `offset`

---

#### `PATCH /complaints/{id}/resolve`

Разрешить жалобу (администратор).

**Поля запроса**:

| Поле | Тип | Обязательное | Описание |
|---|---|---|---|
| `adminId` | string (uuid) | **да** | ID администратора |
| `status` | string | **да** | Новый статус: `RESOLVED`, `REJECTED` |
| `resolution` | string (мин. 5 символов) | **да** | Решение по жалобе |

**Пример запроса**:
```json
{
  "adminId": "uuid-admin",
  "status": "RESOLVED",
  "resolution": "Пользователь предупреждён. Средства возвращены участникам."
}
```

---

#### `GET /health`

```json
{"status": "ok", "service": "reputation-service"}
```

---

### Search Service (порт 4007)

Базовый URL: `http://search-service:4007` (или через Gateway: `/search/...`)

Технология: Go + Elasticsearch

---

#### `POST /search`

Поиск закупок.

**Заголовки**: `X-User-ID: <userId>` (для сохранения истории)

**Поля запроса**:

| Поле | Тип | Обязательное | Описание |
|---|---|---|---|
| `query` | string | **да** | Поисковый запрос |
| `category` | string | нет | Фильтр по категории |
| `city` | string | нет | Фильтр по городу |
| `priceMin` | number | нет | Минимальная сумма |
| `priceMax` | number | нет | Максимальная сумма |
| `page` | integer | нет | Номер страницы (по умолчанию `1`) |
| `perPage` | integer | нет | Количество результатов на страницу (по умолчанию `20`) |

**Пример запроса**:
```json
{
  "query": "куртки зима",
  "category": "clothing",
  "city": "Москва",
  "priceMin": 1000,
  "priceMax": 10000,
  "page": 1,
  "perPage": 20
}
```

**Ответ**:
```json
{
  "success": true,
  "data": {
    "results": [
      {
        "id": "101",
        "title": "Закупка зимних курток",
        "category": "clothing",
        "city": "Москва",
        "status": "open",
        "score": 0.95
      }
    ],
    "total": 42,
    "page": 1,
    "perPage": 20,
    "totalPages": 3
  }
}
```

---

#### `GET /filters`

Список сохранённых фильтров пользователя.

**Заголовки**: `X-User-ID: <userId>` (обязательно)

**Ответ**:
```json
{
  "success": true,
  "data": [
    {
      "id": "uuid-filter",
      "name": "Зимняя одежда в Москве",
      "category": "clothing",
      "city": "Москва",
      "priceMin": 500,
      "priceMax": 5000
    }
  ]
}
```

---

#### `POST /filters`

Сохранить фильтр.

**Заголовки**: `X-User-ID: <userId>` (обязательно)

**Поля запроса**:

| Поле | Тип | Обязательное | Описание |
|---|---|---|---|
| `name` | string | **да** | Название фильтра |
| `category` | string | нет | Категория |
| `city` | string | нет | Город |
| `priceMin` | number | нет | Минимальная сумма |
| `priceMax` | number | нет | Максимальная сумма |

**Пример запроса**:
```json
{
  "name": "Зимняя одежда в Москве",
  "category": "clothing",
  "city": "Москва",
  "priceMin": 500,
  "priceMax": 5000
}
```

**Ответ** (`201 Created`): объект фильтра

---

#### `DELETE /filters/{id}`

Удалить фильтр.

**Заголовки**: `X-User-ID: <userId>` (обязательно)

**Ответ**:
```json
{
  "success": true,
  "message": "filter deleted"
}
```

---

#### `GET /history`

История поиска пользователя.

**Заголовки**: `X-User-ID: <userId>` (обязательно)

**Ответ**:
```json
{
  "success": true,
  "data": [
    {"query": "куртки зима", "searchedAt": "2024-01-15T10:30:00Z"},
    {"query": "ноутбуки", "searchedAt": "2024-01-14T18:00:00Z"}
  ]
}
```

---

#### `GET /health`

```json
{
  "status": "ok",
  "service": "search-service",
  "elasticsearch": true,
  "redis": true
}
```

---

### Analytics Service (порт 4006)

Базовый URL: `http://analytics-service:4006` (или через Gateway: `/analytics/...`)

Технология: FastAPI (Python)

---

#### `GET /health`

```json
{
  "status": "ok",
  "service": "analytics-service",
  "events_processed": 15420
}
```

---

#### `GET /stats/purchases`

Статистика по закупкам.

**Ответ**:
```json
{
  "success": true,
  "data": {
    "total": 500,
    "byStatus": {
      "open": 45,
      "closed": 420,
      "draft": 35
    },
    "avgParticipants": 12.5,
    "avgAmount": 75000
  }
}
```

---

#### `GET /stats/payments`

Статистика по платежам.

---

#### `GET /stats/commissions`

Статистика по комиссиям.

---

#### `GET /stats/escrow`

Статистика по эскроу.

---

#### `GET /stats/reputation`

Статистика по репутации.

---

#### `GET /stats/search`

Статистика поисковых запросов.

---

#### `GET /stats/summary`

Общая сводная статистика по всем категориям.

---

#### `POST /reports/generate`

Сгенерировать отчёты и загрузить в S3.

**Ответ**:
```json
{
  "success": true,
  "message": "Reports generated and uploaded to S3"
}
```

---

#### `GET /reports/purchases/download`

Скачать отчёт по закупкам (XLSX).

**Ответ**: файл `purchases_report.xlsx`

---

#### `GET /reports/payments/download`

Скачать отчёт по платежам (CSV).

**Ответ**: файл `payments_report.csv`

---

#### `GET /reports/votes/download`

Скачать отчёт по голосованиям (XLSX).

**Ответ**: файл `votes_report.xlsx`

---

### Notification Service (порт 4005)

Базовый URL: `http://notification-service:4005` (или через Gateway: `/notifications/...`)

Технология: Node.js / Express

Сервис уведомлений работает преимущественно на базе Kafka-событий и рассылает уведомления по следующим каналам:
- **Email** — через SMTP
- **WebSocket** — через Centrifugo
- **Web Push** — через VAPID
- **Telegram** — через Telegram Bot API
- **WhatsApp** — через WhatsApp Business API

Внутренние API-эндпоинты используются другими сервисами через Kafka для отправки уведомлений.

---

### Gateway (порт 3000)

Gateway — это обратный прокси (Go), который:
- Валидирует JWT-токены
- Применяет rate-limiting
- Маршрутизирует запросы к микросервисам
- Поддерживает CORS

**Таблица маршрутизации**:

| Префикс пути (Gateway) | Целевой сервис | Примечание |
|---|---|---|
| `/api/v1/auth/*` | Auth Service (4001) | Публичный (без JWT) |
| `/api/v1/purchases/*` | Purchase Service (4002) | Требует JWT |
| `/api/v1/voting/*` | Purchase Service (4002) | Требует JWT |
| `/api/v1/payments/*` | Payment Service (4003) | Требует JWT |
| `/api/v1/escrow/*` | Payment Service (4003) | Требует JWT |
| `/api/v1/commission/*` | Payment Service (4003) | Требует JWT |
| `/api/v1/chat/*` | Chat Service (4004) | Требует JWT |
| `/api/v1/search/*` | Search Service (4007) | Требует JWT |
| `/api/v1/reputation/*` | Reputation Service (4008) | Требует JWT |
| `/api/v1/reviews/*` | Reputation Service (4008) | Требует JWT |
| `/api/v1/complaints/*` | Reputation Service (4008) | Требует JWT |
| `/api/v1/analytics/*` | Analytics Service (4006) | Требует JWT |
| `/ws/*` | Chat Service (4004) | WebSocket (Centrifugo) |
| `/webhooks/*` | Payment Service (4003) | Без JWT (проверка подписи) |

---

---

*Документ актуализирован на основе исходного кода проекта. При обновлении API рекомендуется своевременно обновлять этот файл.*

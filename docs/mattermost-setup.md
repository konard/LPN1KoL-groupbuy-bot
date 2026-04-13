# Настройка интеграции с Mattermost

Это руководство описывает, как настроить Mattermost так, чтобы он слушал ваш сервис GroupBuy и бот работал так же, как в Telegram.

---

## Как это работает

GroupBuy-бот в Mattermost использует три механизма интеграции:

```
Mattermost сервер
      │
      │  Outgoing Webhook / Slash Command
      │  (POST http://<ваш-сервер>:8002/webhook)
      ▼
Mattermost Adapter (порт 8002)
      │
      │  Стандартизованное сообщение
      ▼
Bot Service (порт 8001)
      │
      │  Ответ через POST /send
      ▼
Mattermost Adapter (порт 8002)
      │
      │  Incoming Webhook / REST API
      ▼
Mattermost сервер → пользователь видит ответ
```

**Компоненты:**

- **Outgoing Webhooks** — Mattermost отправляет сообщения пользователей на адаптер.
- **Incoming Webhook** — адаптер отправляет ответы обратно в Mattermost.
- **Slash Commands** — команды вида `/start`, `/help` и т.д.
- **Bot Account + REST API** (опционально) — отправка личных сообщений пользователям напрямую.

---

## Шаг 1. Запустите сервисы GroupBuy

Убедитесь, что сервисы работают:

```bash
docker-compose up -d
```

Mattermost адаптер будет доступен на порту `8002`. Убедитесь, что порт `8002` открыт в брандмауэре:

```bash
# Ubuntu / Debian (ufw)
sudo ufw allow 8002/tcp

# Или iptables
sudo iptables -A INPUT -p tcp --dport 8002 -j ACCEPT
```

> **Важно:** порт `8002` должен быть доступен с вашего Mattermost-сервера. Если Mattermost и GroupBuy находятся на разных серверах, используйте публичный IP-адрес сервера GroupBuy.

---

## Шаг 2. Создайте Incoming Webhook в Mattermost

Это нужно, чтобы адаптер мог отправлять ответы пользователям.

1. Войдите в Mattermost как администратор.
2. Откройте **Главное меню → Интеграции → Входящие вебхуки** (Incoming Webhooks).
3. Нажмите **Добавить входящий вебхук**.
4. Выберите канал (например, `Town Square`) — используется по умолчанию; конкретный канал можно переопределять в каждом сообщении.
5. Нажмите **Сохранить**.
6. Скопируйте **URL вебхука** — он выглядит примерно так:
   ```
   https://your-mattermost.example.com/hooks/abc123xyz
   ```

---

## Шаг 3. Создайте Outgoing Webhook в Mattermost

Это нужно, чтобы Mattermost отправлял сообщения пользователей в адаптер.

1. Откройте **Главное меню → Интеграции → Исходящие вебхуки** (Outgoing Webhooks).
2. Нажмите **Добавить исходящий вебхук**.
3. Заполните поля:
   - **Тип контента (Content Type):** `application/x-www-form-urlencoded`
   - **Канал:** выберите канал или оставьте пустым (будут обрабатываться все каналы)
   - **Триггерные слова (Trigger Words):** оставьте пустым — бот будет получать все сообщения
   - **URL обратного вызова (Callback URL):**
     ```
     http://<IP-АДРЕС-ВАШЕГО-СЕРВЕРА>:8002/webhook
     ```
     Например: `http://185.100.200.50:8002/webhook`
4. Нажмите **Сохранить**.
5. Скопируйте сгенерированный **Токен** (Token) — он нужен для проверки подлинности запросов.

---

## Шаг 4. Добавьте Slash Commands (опционально, но рекомендуется)

Slash Commands позволяют пользователям вводить команды вида `/start`, `/help` прямо в строке ввода Mattermost.

Для каждой команды:

1. Откройте **Главное меню → Интеграции → Slash Commands**.
2. Нажмите **Добавить Slash Command**.
3. Заполните поля:
   - **Команда (Command):** например, `/start`
   - **Request URL:**
     ```
     http://<IP-АДРЕС-ВАШЕГО-СЕРВЕРА>:8002/slash
     ```
   - **Request Method:** `POST`
   - **Response Username:** `groupbuy-bot` (произвольное имя)
4. Нажмите **Сохранить** и скопируйте **Токен**.

Повторите для каждой нужной команды: `/help`, `/procurements`, `/my_procurements`, `/search`, `/create_procurement`, `/profile`, `/balance`, `/deposit`, `/notifications`, `/chat`, `/status`.

> **Примечание:** токен от Slash Commands и от Outgoing Webhook должен совпадать или вы можете использовать один и тот же токен, настроив одно значение `MATTERMOST_TOKEN`.

---

## Шаг 5. Создайте Bot Account (опционально, но рекомендуется)

Bot Account позволяет боту отправлять **личные сообщения** пользователям напрямую, вместо публичного канала.

1. Откройте **Главное меню → Интеграции → Bot Accounts**.
2. Нажмите **Добавить Bot Account**.
3. Заполните:
   - **Имя пользователя (Username):** `groupbuy-bot`
   - **Роль:** `Member`
4. Нажмите **Создать Bot Account**.
5. Скопируйте **Personal Access Token** — он отображается только один раз.

---

## Шаг 6. Настройте переменные окружения

Откройте файл `.env` в корне проекта и заполните переменные Mattermost:

```env
# Токен из Outgoing Webhook или Slash Command (для верификации запросов)
MATTERMOST_TOKEN=ваш-токен-исходящего-вебхука

# URL входящего вебхука (для отправки ответов в Mattermost)
MATTERMOST_WEBHOOK_URL=https://your-mattermost.example.com/hooks/abc123xyz

# Публичный URL этого адаптера (должен быть доступен с Mattermost-сервера)
# Если Mattermost на другом сервере — укажите публичный IP:
MATTERMOST_ADAPTER_URL=http://185.100.200.50:8002

# Опционально — нужно для Bot Account и личных сообщений:
MATTERMOST_BOT_TOKEN=ваш-personal-access-token-бота
MATTERMOST_URL=https://your-mattermost.example.com
```

---

## Шаг 7. Перезапустите адаптер

```bash
docker-compose restart mattermost-adapter
```

Проверьте логи:

```bash
docker-compose logs -f mattermost-adapter
```

Вы должны увидеть:
```
Starting Mattermost adapter on 0.0.0.0:8002 …
```

---

## Шаг 8. Проверьте работу

1. Откройте любой канал в Mattermost.
2. Введите `/start` или просто напишите сообщение.
3. Бот должен ответить приветствием и меню, как в Telegram.

Если ответа нет — смотрите раздел [Устранение неполадок](#устранение-неполадок).

---

## Доступные команды

Все команды работают так же, как в Telegram:

| Команда | Описание |
|---|---|
| `/start` | Запуск бота, приветствие и главное меню |
| `/help` | Список всех доступных команд |
| `/procurements` | Список активных закупок |
| `/my_procurements` | Мои закупки (организованные и участие) |
| `/search` | Поиск закупок по ключевым словам |
| `/create_procurement` | Создать закупку (только для организаторов) |
| `/profile` | Просмотр и редактирование профиля |
| `/balance` | Проверка баланса |
| `/deposit` | Пополнение баланса |
| `/notifications` | Просмотр уведомлений |
| `/chat` | Войти в чат закупки |
| `/status` | Статус бота |

---

## Интерактивные кнопки

В Telegram бот использует inline-клавиатуры. В Mattermost те же кнопки отображаются как **attachment actions** (кнопки под сообщением). При нажатии выполняется то же действие, что и при нажатии кнопки в Telegram.

---

## Схема сетевого доступа

```
Mattermost Server  ──────►  GroupBuy Adapter  (порт 8002)
  (публичный IP)               (ваш сервер)

GroupBuy Adapter   ──────►  Bot Service         (порт 8001, внутренний)
GroupBuy Adapter   ──────►  Mattermost Server   (входящий вебхук / REST API)
```

**Требования к сетевому доступу:**

| Соединение | Порт | Открыт для |
|---|---|---|
| Mattermost → GroupBuy Adapter | `8002` | Mattermost-сервер |
| GroupBuy Adapter → Mattermost | `443` или `80` | Интернет |
| Bot Service ↔ Adapter | `8001` | Внутренний Docker |

---

## Устранение неполадок

### Бот не отвечает

1. Проверьте, что адаптер запущен:
   ```bash
   docker-compose ps mattermost-adapter
   curl http://localhost:8002/health
   ```
   Ожидаемый ответ: `{"status": "ok"}`

2. Проверьте логи адаптера:
   ```bash
   docker-compose logs mattermost-adapter
   ```

3. Убедитесь, что `MATTERMOST_TOKEN` в `.env` совпадает с токеном в настройках Outgoing Webhook.

4. Убедитесь, что `MATTERMOST_ADAPTER_URL` содержит публичный IP-адрес, доступный с Mattermost-сервера.

5. Проверьте доступность порта с Mattermost-сервера:
   ```bash
   # Выполните на Mattermost-сервере:
   curl http://<IP-АДРЕС-GROUPBUY>:8002/health
   ```

### Ошибка "Webhook token mismatch"

Токен в `.env` (`MATTERMOST_TOKEN`) не совпадает с токеном в настройках Outgoing Webhook в Mattermost. Скопируйте токен из **Интеграции → Исходящие вебхуки → [ваш вебхук] → Токен** и обновите `.env`.

### Бот отвечает в канал, а не в личные сообщения

Настройте Bot Account (Шаг 5) и добавьте `MATTERMOST_BOT_TOKEN` и `MATTERMOST_URL` в `.env`. После этого бот будет отвечать личными сообщениями.

### Slash команды возвращают "command not found"

Убедитесь, что команды зарегистрированы в **Интеграции → Slash Commands** и URL указывает на `http://<ваш-сервер>:8002/slash`.

---

## Пример полной конфигурации `.env`

```env
# === Mattermost ===
MATTERMOST_TOKEN=abc123def456ghi789
MATTERMOST_WEBHOOK_URL=https://mattermost.mycompany.com/hooks/xyz987wvu654
MATTERMOST_ADAPTER_URL=http://185.100.200.50:8002
MATTERMOST_BOT_TOKEN=bot_personal_access_token_here
MATTERMOST_URL=https://mattermost.mycompany.com
```

---

## Дополнительные ресурсы

- [Официальная документация Mattermost: Outgoing Webhooks](https://developers.mattermost.com/integrate/webhooks/outgoing/)
- [Официальная документация Mattermost: Incoming Webhooks](https://developers.mattermost.com/integrate/webhooks/incoming/)
- [Официальная документация Mattermost: Slash Commands](https://developers.mattermost.com/integrate/slash-commands/)
- [Официальная документация Mattermost: Bot Accounts](https://developers.mattermost.com/integrate/reference/bot-accounts/)
- [Общая инструкция по развёртыванию GroupBuy](./deployment.md)

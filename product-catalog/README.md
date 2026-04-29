# Каталог продуктов

Полнофункциональное веб-приложение для управления каталогом продуктов.

## Стек технологий

- **Бэкенд**: FastAPI (Python 3.11), SQLAlchemy ORM, JWT-аутентификация, паттерн Repository
- **Фронтенд**: React 18, Vite, Axios
- **База данных**: PostgreSQL 16 (или SQLite для локальной разработки)
- **Логирование**: Python `logging` (файл + stdout)
- **Курс валют**: API Национального банка РБ (`api.nbrb.by/exrates`)

## Быстрый запуск с Docker

```bash
# 1. Перейдите в папку проекта
cd product-catalog

# 2. Скопируйте файл переменных окружения
cp .env.example .env
# При необходимости измените SECRET_KEY в .env

# 3. Запустите все сервисы
docker compose up -d

# 4. Откройте браузер
open http://localhost
```

После запуска база данных автоматически заполняется тестовыми данными.

## Тестовые учётные записи

| Логин      | Пароль       | Роль                      |
|------------|--------------|---------------------------|
| `admin`    | `admin123`   | Администратор             |
| `advanced` | `advanced123`| Продвинутый пользователь  |
| `user`     | `user123`    | Простой пользователь      |

## Локальная разработка (без Docker)

### Требования
- Python 3.11+
- Node.js 20+
- PostgreSQL 14+ (или будет использоваться SQLite автоматически)

### Бэкенд

```bash
cd product-catalog/backend

# Создайте виртуальное окружение
python -m venv .venv
source .venv/bin/activate        # Linux/macOS
# .venv\Scripts\activate         # Windows

# Установите зависимости
pip install -r requirements.txt

# Настройте переменные окружения (опционально — без них используется SQLite)
export DATABASE_URL="postgresql://user:pass@localhost:5432/product_catalog"
export SECRET_KEY="my-secret-key"

# Запустите сервер
uvicorn main:app --reload --port 8000
```

API будет доступен по адресу: http://localhost:8000  
Документация Swagger: http://localhost:8000/docs

### Фронтенд

```bash
cd product-catalog/frontend

# Установите зависимости
npm install

# Запустите dev-сервер (прокси на http://localhost:8000)
npm run dev
```

Приложение откроется на http://localhost:5173

## Структура проекта

```
product-catalog/
├── backend/
│   ├── main.py          # FastAPI приложение, модели, репозитории, роуты
│   ├── requirements.txt
│   └── Dockerfile
├── frontend/
│   ├── src/
│   │   ├── App.jsx              # Корневой компонент, навигация
│   │   ├── api.js               # Axios-клиент с interceptors
│   │   ├── hooks/
│   │   │   └── useRole.js       # Хук для проверки роли пользователя
│   │   ├── components/
│   │   │   ├── PriceCell.jsx    # Ячейка цены со звёздочкой и tooltip USD
│   │   │   ├── Modal.jsx        # Универсальный модальный компонент
│   │   │   └── ProductForm.jsx  # Форма создания/редактирования продукта
│   │   └── pages/
│   │       ├── LoginPage.jsx    # Страница входа
│   │       ├── CatalogPage.jsx  # Каталог продуктов с поиском/фильтрацией
│   │       ├── CategoriesPage.jsx # Управление категориями
│   │       └── AdminPage.jsx    # Панель управления пользователями
│   ├── package.json
│   ├── vite.config.js
│   ├── nginx.conf
│   └── Dockerfile
├── docker-compose.yml
├── .env.example
└── README.md
```

## Функциональность

### Роли пользователей

| Действие                        | simple_user | advanced_user | admin |
|---------------------------------|:-----------:|:-------------:|:-----:|
| Просмотр каталога               | ✓           | ✓             | ✓     |
| Просмотр специального примечания| ✗           | ✓             | ✓     |
| Создание продукта               | ✓           | ✓             | ✓     |
| Изменение продукта              | ✓           | ✓             | ✓     |
| Удаление продукта               | ✗           | ✓             | ✓     |
| CRUD категорий                  | ✗           | ✓             | ✓     |
| Управление пользователями       | ✗           | ✗             | ✓     |

### API бэкенда

| Метод | Путь                          | Описание                               |
|-------|-------------------------------|----------------------------------------|
| POST  | `/auth/login`                 | Вход, возвращает access + refresh токены |
| POST  | `/auth/refresh`               | Обновление access-токена               |
| GET   | `/auth/me`                    | Информация о текущем пользователе      |
| GET   | `/categories`                 | Список категорий                       |
| POST  | `/categories`                 | Создать категорию (advanced+)          |
| PUT   | `/categories/{id}`            | Изменить категорию (advanced+)         |
| DELETE| `/categories/{id}`            | Удалить категорию + каскад (advanced+) |
| GET   | `/products`                   | Список продуктов (поиск, фильтр)       |
| POST  | `/products`                   | Создать продукт                        |
| PUT   | `/products/{id}`              | Изменить продукт                       |
| DELETE| `/products/{id}`              | Удалить продукт (advanced+)            |
| GET   | `/convert-usd?amount=10.0`    | Конвертация BYN → USD через НБРБ      |
| GET   | `/admin/users`                | Список пользователей (admin)           |
| POST  | `/admin/users`                | Создать пользователя (admin)           |
| PATCH | `/admin/users/{id}/block`     | Блокировать/разблокировать (admin)     |
| DELETE| `/admin/users/{id}`           | Удалить пользователя (admin)           |
| PATCH | `/admin/users/{id}/password`  | Изменить пароль (admin)                |

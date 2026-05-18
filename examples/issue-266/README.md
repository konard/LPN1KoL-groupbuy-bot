# Issue 266

В папке собраны три части тестового задания из Google Doc.

## Laravel API collector

```bash
cd examples/issue-266/laravel
composer install
cp .env.example .env
php artisan key:generate
touch database/database.sqlite
php artisan migrate
php artisan schedule:work
php artisan serve
```

Команда `php artisan api-records:fetch` получает данные из `https://official-joke-api.appspot.com/random_joke` и сохраняет их в таблицу `external_api_records`. Планировщик запускает команду каждые 5 минут через `routes/console.php`.

JSON API:

```text
GET /api/api-records
```

## Фильтрация полей по типу

Файл `type-field-filter.js` подключается на страницу `http://test.amopoint-dev.ru/testzz/testlist.html` или вставляется в консоль браузера. Скрипт оставляет видимым поле `Тип` и показывает только те элементы, у которых значение выбранного пункта содержится в атрибуте `name`.

Алгоритмы:

- Выбран прямой обход элементов формы и проверка `name.includes(value)`, потому что страница статическая, а условие задания требует поиск подстроки в `name`.
- jQuery не используется, потому что для этой задачи достаточно стандартного DOM API, а дополнительная библиотека не дает выигрыша.
- Регулярные выражения не используются, потому что нужно простое вхождение строки, а не шаблон с границами или группами.
- Таблица соответствий `тип -> поля` не используется, потому что соответствие уже закодировано в атрибутах `name`.

## Visitor counter

Клиентский скрипт:

```html
<script src="https://example.com/js/visitor-counter.js" data-endpoint="https://example.com/api/visits"></script>
```

Скрипт собирает `ip`, `city`, `device`, `visitor_id`, адрес страницы и referrer, после чего отправляет данные на сервер. Если геолокационный API недоступен, сервер все равно сохранит посещение и подставит IP из запроса.

Статистика доступна после авторизации:

```text
GET /stats/login
```

Пароль задается переменной окружения `VISITOR_STATS_PASSWORD`. Страница `/stats` показывает график уникальных посещений по часам и круговую диаграмму по городам.

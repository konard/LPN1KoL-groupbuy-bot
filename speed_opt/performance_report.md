# performance_report.md

## Контекст анализа

Анализ выполнен по архиву проекта `1c8_private-master.zip` и дампу `alfastok_db_1c8_8.sql` из папки Google Drive, указанной в задании. Проект — Laravel 10 / PHP 8.1+ с MySQL 8, Vite, Filament/Livewire и B2B-каталогом. Импорт дампа в Docker/MySQL не производился; выводы по базе данных сделаны статически по DDL и INSERT-блокам дампа.

Ключевые размеры из дампа: 101 таблица. Самые крупные: `cookie_consents` — 2 168 684 строк, `item_price_type` — 822 549, `sale_products` — 334 131, `item_order` — 219 739, `attribute_item` — 115 603, `item_price` — 95 243, `sales` — 60 929, `amount_item` — 50 676, `items` — 22 337, `categories` — 1 385.

Схема товаров в дампе: цены и остатки в `item_price`, `item_price_type`, `amount_item` по `item_uuid`; FULLTEXT-индекс `items_name_synonyms_fulltext` по `items(name, synonyms)` уже существует; архивного флага `in_archive` и прямого поля `price` в `items` нет.

---

## Выявленные узкие места

### 🗄️ База данных и запросы

| # | Проблема | Расположение | Почему замедляет | Масштаб |
|---|---------|-------------|-----------------|---------|
| 1 | На каждый визит создаётся или читается строка `pending` в `cookie_consents` даже до выбора пользователя | `app/Objects/CookieConsentManager.php`, таблица `cookie_consents` | Самая большая таблица в БД (2.1 M строк) получает INSERT/SELECT на каждый pageview; hot index, lock waits при пиковой нагрузке | **critical** |
| 2 | У `cookie_consents` нет составного индекса по `(status, date)` и `(profile_id, status, date)` | DDL `cookie_consents` | Cleanup-запросы и аналитика по статусу делают full scan 2.1 M строк | **high** |
| 3 | В каталоге итоговый `get()` тянет весь набор товаров категории; `groupBy()` выполняется в PHP | `app/Http/Controllers/Catalogue/Queries/Catalogue.php` | При крупных категориях в PHP попадают тысячи объектов Eloquent, растёт пиковое потребление памяти | **high** |
| 4 | `ItemRepository::catalogue()` собирает полную карточку товара (цены, остатки, скидки, аналоги, атрибуты, характеристики, гайды, изображения, сегменты) для каждой строки в списке | `app/Repositories/ItemRepository.php` | Каждый запрос к списку делает десятки JOIN и подзапросов там, где нужны только базовые поля | **critical** |
| 5 | Отсутствуют прикладные индексы для частых фильтров и JOIN: `items(category_id_1c, type)`, `items(id_1c)`, `items(vendor_code)`, `items(barcode)`, `categories(id_1c)`, `categories(parent_id_1c)`, `categories(parent_uuid, is_hide, default_sort)`, `sales(uuid_contractor, id)` | DDL дампа, код репозиториев | Повторяющиеся фильтры делают full scan или index scan по некомпозитным индексам | **high** |
| 6 | Генерация YML/Excel прайса загружает весь набор товаров и весь файл в памяти одного PHP-процесса | `app/Http/Controllers/Price/Index.php`, `app/Http/Controllers/Price/Base.php` | При 22 000 товаров потребление памяти на один HTTP-worker может превышать сотни MB; worker блокирован до конца генерации | **high** |
| 7 | `HomeController::index()` вызывает `get(['id'])->count()` для новых товаров, грузит все отзывы и все receipts без LIMIT | `app/Http/Controllers/HomeController.php` | Лишние полные выборки и перенос подсчёта из SQL в PHP | **medium** |
| 8 | Сессии и кеш хранятся в файловой системе (`SESSION_DRIVER=file`, `CACHE_DRIVER=file`) | `config/cache.php`, `config/session.php` | При высокой посещаемости — конкуренция за файловые дескрипторы; нет поддержки тегов кеша | **high** |
| 9 | Очереди синхронные (`QUEUE_CONNECTION=sync`) | `config/queue.php` | Экспорт, письма, импорт изображений и внешние API блокируют HTTP-запрос | **high** |

### 🔍 Поиск

| # | Проблема | Расположение | Почему замедляет | Масштаб |
|---|---------|-------------|-----------------|---------|
| 10 | Быстрый поиск использует `LIKE '%слово%'`, хотя FULLTEXT-индекс `items_name_synonyms_fulltext` уже существует | `app/Http/Controllers/Search/FastSearch.php` | `LIKE '%...%'` не может использовать индекс — всегда full scan по 22 000 товаров | **high** |
| 11 | `HomeController::search()` использует `get()->count()` вместо `count()` и содержит поля, которых нет в схеме дампа | `app/Http/Controllers/HomeController.php` | Грузит сотни/тысячи объектов Eloquent, чтобы посчитать строки на стороне PHP | **high** |

### 📂 Каталог

| # | Проблема | Расположение | Почему замедляет | Масштаб |
|---|---------|-------------|-----------------|---------|
| 12 | Список категорий используется через `get()` без пагинации, а потом `groupBy` на PHP | `Catalogue/Queries/Catalogue.php` | Одна страница каталога может инициировать выборку всех товаров категории | **high** |
| 13 | Нет отдельных queries для list-view и detail-view; страница списка запрашивает данные для детальной страницы | `app/Repositories/ItemRepository.php` | Избыточные JOIN, подзапросы и eager-load при каждом рендере страницы списка | **critical** |

### 🎨 Фронтенд и ассеты

| # | Проблема | Расположение | Почему замедляет | Масштаб |
|---|---------|-------------|-----------------|---------|
| 14 | Нет файла `vite.config.js`; production build невозможно воспроизвести по архиву | корень проекта | Без Vite-конфига нет минификации, tree shaking, code splitting | **high** |
| 15 | Layout одновременно подключает `app.scss`, `private.scss`, `public.scss` | `resources/views/layouts/app.blade.php`, `layouts/open.blade.php` | Повышенный CSS payload и дублирование правил | **medium** |
| 16 | Тяжёлые JS-модули (`jquery-ui.min.js`, inputmask, fancybox) подключаются глобально на всех страницах | `resources/js`, `layouts/open.blade.php` | Лишняя нагрузка на парсинг и выполнение JS на страницах, где они не нужны | **medium** |
| 17 | Шрифты в форматах TTF/EOT/OTF/SVG без WOFF2-subset-стратегии | `resources/fonts`, `_fonts.scss` | Устаревшие форматы, большой размер загрузки, нет `font-display: swap` | **medium** |
| 18 | В `public/.htaccess` нет правил долгого кеширования статики, gzip/brotli, image/font cache headers | `public/.htaccess` | Повторные посещения не используют браузерный кеш | **medium** |

### ⚙️ Серверная логика и кеширование

| # | Проблема | Расположение | Почему замедляет | Масштаб |
|---|---------|-------------|-----------------|---------|
| 19 | `APP_DEBUG=true`, `LOG_LEVEL=debug`, `CACHE_DRIVER=file`, `SESSION_DRIVER=file`, `QUEUE_CONNECTION=sync` | `.env.example`, `config/*.php` | Dev-режим в production добавляет stack trace, verbose logging, disk I/O на каждый запрос | **critical** |
| 20 | Синхронные вызовы внешних API, генерация PDF/Excel без очереди | контроллеры экспорта | Блокируют HTTP-worker до завершения | **high** |
| 21 | Нет кеша для часто запрашиваемых данных (категории, настройки, типы цен) | репозитории, `setting()` helper | Повторяющиеся SQL-запросы на каждый запрос без TTL-кеша | **high** |
| 22 | Нет `ItemCardRepository` или аналогичного кеша карточки товара | `ItemRepository.php` | Ценная выборка повторяется для каждого товара на каждой странице каталога | **high** |

### 🔐 Сессии и аутентификация

| # | Проблема | Расположение | Почему замедляет | Масштаб |
|---|---------|-------------|-----------------|---------|
| 23 | Сессии в файловой системе: нет cache tags, есть файловые блокировки | `config/session.php` | При высокой нагрузке — lock contention на файлы сессий | **high** |
| 24 | Избыточные проверки прав/политик в циклах (потенциально) | middleware, Blade-компоненты | Каждая проверка может обращаться к БД или вычислять права заново | **medium** |

### 🪵 Логирование и отладка

| # | Проблема | Расположение | Почему замедляет | Масштаб |
|---|---------|-------------|-----------------|---------|
| 25 | Активные `dd()` в production-коде | `HomeController::emailFeedback()`, `app/Models/Model.php`, `app/Objects/Pipes_/Price/ToCurrency.php`, `Livewire/Cart/Item/Delete.php` | Могут остановить выполнение запроса в production-ветке | **critical** |
| 26 | `APP_DEBUG=true` включает debug toolbar и расширенное логирование | `.env.example`, Debugbar / Telescope | Значительный overhead на каждый запрос при production-нагрузке | **critical** |
| 27 | Избыточное логирование уровня `debug` в production | `config/logging.php`, `LOG_LEVEL=debug` | Disk I/O на запись логов на каждый запрос | **medium** |

### ⚠️ Прочие проблемы

| # | Проблема | Расположение | Почему замедляет | Масштаб |
|---|---------|-------------|-----------------|---------|
| 28 | Устаревший `Price/Index.php` оперирует полями, которых нет в дампе | `app/Http/Controllers/Price/Index.php` | Код ищет несуществующие поля → silent bugs или неоптимальные OR-условия | **high** |
| 29 | Нет nginx/Apache production-конфига с gzip/brotli и cache headers | `public/.htaccess`, отсутствует nginx-конфиг | Нет сжатия ответов, нет долгого кеша для статики | **high** |
| 30 | Нет APM и slow query log | инфраструктура | Без метрик невозможно подтвердить улучшения и найти новые узкие места | **medium** |

---

## Конкретные меры по ускорению

### 1. Production env, кеш, сессии, очереди

**Что изменить:** `.env.production`, `config/cache.php`, `config/session.php`, `config/queue.php`.

```dotenv
APP_ENV=production
APP_DEBUG=false
LOG_LEVEL=warning

CACHE_DRIVER=redis
CACHE_STORE=redis
SESSION_DRIVER=redis
QUEUE_CONNECTION=redis

REDIS_CLIENT=phpredis
REDIS_HOST=127.0.0.1
REDIS_PORT=6379
REDIS_CACHE_DB=1
REDIS_SESSION_DB=2
REDIS_QUEUE_DB=3
```

```bash
composer install --no-dev --prefer-dist --optimize-autoloader
php artisan optimize:clear
php artisan config:cache
php artisan route:cache
php artisan view:cache
php artisan event:cache
php artisan queue:restart
```

---

### 2. Cookie consent — не писать `pending` в БД до действия пользователя

**Что изменить:** `app/Objects/CookieConsentManager.php`, миграция, cleanup-команда.

```php
// Миграция: database/migrations/2026_05_03_000001_optimize_cookie_consents.php
Schema::table('cookie_consents', function (Blueprint $table) {
    $table->index(['status', 'date'], 'cookie_consents_status_date_idx');
    $table->index(['profile_id', 'status', 'date'], 'cookie_consents_profile_status_date_idx');
});
```

```php
// app/Objects/CookieConsentManager.php — новая версия
final class CookieConsentManager
{
    private const TOKEN_COOKIE = 'cookie_consent_token';

    public function state(Request $request): CookieConsents
    {
        $token = $request->cookie(self::TOKEN_COOKIE);
        if (!$token) {
            return CookieConsents::Pending;
        }

        $consent = CookieConsent::query()
            ->select(['status'])
            ->where('token', $token)
            ->whereIn('status', [CookieConsents::Accepted->value, CookieConsents::Rejected->value])
            ->latest('date')
            ->first();

        return $consent?->status ?? CookieConsents::Pending;
    }

    public function accept(Request $request): CookieConsent
    {
        return $this->storeDecision($request, CookieConsents::Accepted);
    }

    public function reject(Request $request): CookieConsent
    {
        return $this->storeDecision($request, CookieConsents::Rejected);
    }

    private function token(Request $request): string
    {
        $token = $request->cookie(self::TOKEN_COOKIE) ?: (string) Str::uuid();
        Cookie::queue(cookie(self::TOKEN_COOKIE, $token, 60 * 24 * 365, secure: true, httpOnly: true, sameSite: 'lax'));
        return $token;
    }

    private function storeDecision(Request $request, CookieConsents $status): CookieConsent
    {
        $token = $this->token($request);
        return CookieConsent::query()->updateOrCreate(
            ['token' => $token],
            ['profile_id' => profile()?->id, 'ip' => $request->ip(),
             'session_id' => $request->session()->getId(), 'status' => $status->value, 'date' => now()],
        );
    }
}
```

```php
// app/Console/Commands/PruneCookieConsents.php
protected $signature = 'cookie-consents:prune {--pending-days=7} {--rejected-days=180}';

public function handle(): int
{
    $pending = CookieConsent::query()
        ->where('status', CookieConsents::Pending->value)
        ->where('date', '<', now()->subDays((int) $this->option('pending-days')))
        ->delete();

    $rejected = CookieConsent::query()
        ->where('status', CookieConsents::Rejected->value)
        ->where('date', '<', now()->subDays((int) $this->option('rejected-days')))
        ->delete();

    $this->info("Deleted pending={$pending}, rejected={$rejected}");
    return self::SUCCESS;
}
```

```php
// app/Console/Kernel.php
$schedule->command('cookie-consents:prune --pending-days=7 --rejected-days=180')
    ->dailyAt('03:20')
    ->withoutOverlapping();
```

---

### 3. Индексы для каталога, поиска и истории продаж

**Что изменить:** новая миграция `database/migrations/2026_05_03_000002_add_performance_indexes.php`.

```sql
-- Проверить план до добавления:
EXPLAIN SELECT id, uuid, id_1c, name FROM items
WHERE category_id_1c = '3149' AND type = 'product' ORDER BY name LIMIT 40;

-- Добавить индексы:
ALTER TABLE items
    ADD INDEX idx_items_category_id_1c_type (category_id_1c, type),
    ADD INDEX idx_items_id_1c (id_1c),
    ADD INDEX idx_items_vendor_code (vendor_code),
    ADD INDEX idx_items_barcode (barcode);

ALTER TABLE categories
    ADD INDEX idx_categories_id_1c (id_1c),
    ADD INDEX idx_categories_parent_id_1c (parent_id_1c),
    ADD INDEX idx_categories_parent_hide_sort (parent_uuid, is_hide, default_sort);

ALTER TABLE sales
    ADD INDEX idx_sales_uuid_contractor_id (uuid_contractor, id);
```

---

### 4. Поиск: FULLTEXT вместо LIKE, точные коды по индексам

**Что изменить:** `app/Http/Controllers/Search/FastSearch.php`.

```php
// Было:
$items = Item::query()
    ->where('name', 'LIKE', "%{$term}%")
    ->limit(10)->get();

// Стало:
$booleanTerm = collect(preg_split('/\s+/u', $term))
    ->filter()
    ->map(fn (string $word) => '+' . $word . '*')
    ->implode(' ');

$items = Item::query()
    ->select(['id', 'id_1c', 'uuid', 'name', 'vendor_code', 'barcode'])
    ->available()
    ->notCheap()
    ->where(function ($query) use ($term, $booleanTerm) {
        $query->where('vendor_code', $term)
            ->orWhere('barcode', $term)
            ->orWhere('id_1c', $term)
            ->orWhereFullText(['name', 'synonyms'], $booleanTerm, ['mode' => 'boolean']);
    })
    ->orderByRaw("CASE WHEN vendor_code = ? OR barcode = ? OR id_1c = ? THEN 0 ELSE 1 END",
        [$term, $term, $term])
    ->limit(10)
    ->get();
```

**Что изменить:** `app/Http/Controllers/HomeController.php` — заменить `get()->count()` на `count()`.

```php
// Было:
$count = Item::query()->where(...)->get()->count();

// Стало:
$booleanTerm = collect(preg_split('/\s+/u', $term))->filter()
    ->map(fn ($w) => "+{$w}*")->implode(' ');

$baseQuery = Item::query()->where(function ($q) use ($booleanTerm, $term) {
    $q->whereFullText(['name', 'synonyms'], $booleanTerm, ['mode' => 'boolean'])
        ->orWhere('vendor_code', $term)
        ->orWhere('barcode', $term)
        ->orWhere('id_1c', $term);
});

$availableCount = (clone $baseQuery)->whereExists(fn ($q) =>
    $q->selectRaw('1')->from('amount_item')
        ->whereColumn('amount_item.item_uuid', 'items.uuid')
        ->where('amount_item.amount_id', 1)
        ->whereRaw('CAST(amount_item.value AS DECIMAL(12,3)) > 0')
)->count();

$totalCount = (clone $baseQuery)->count();
$items = (clone $baseQuery)->available()->notCheap()->orderBy('name')->paginate(24);
```

---

### 5. Каталог: list-view отдельно от detail-view

**Что изменить:** `app/Repositories/ItemRepository.php`, `Catalogue/Queries/Catalogue.php`.

```php
// app/Repositories/ItemRepository.php
public function catalogueList(Builder $query, int $perPage = 24): LengthAwarePaginator
{
    return $query
        ->select([
            'items.id', 'items.id_1c', 'items.uuid', 'items.category_uuid',
            'items.name', 'items.vendor_code', 'items.barcode',
            'items.brand_uuid', 'items.price_group_uuid', 'items.updated_at',
        ])
        ->available()
        ->notCheap()
        ->selectSub(
            DB::table('amount_item')
                ->select('amount_item.value')
                ->whereColumn('amount_item.item_uuid', 'items.uuid')
                ->where('amount_item.amount_id', 1)
                ->limit(1),
            'amount_value',
        )
        ->selectSub(
            DB::table('item_images')
                ->select('item_images.image_sm')
                ->whereColumn('item_images.item_uuid', 'items.uuid')
                ->orderBy('item_images.id')
                ->limit(1),
            'image_sm',
        )
        ->orderBy('items.name')
        ->paginate($perPage);
}

public function catalogueDetail(string $uuid): Item
{
    return Item::query()
        ->where('items.uuid', $uuid)
        ->with(['brand', 'images', 'attributes.attribute', 'characteristics', 'guides', 'schemes', 'segments'])
        ->firstOrFail();
}
```

```php
// Catalogue/Queries/Catalogue.php
public function __invoke(CatalogueRequest $request, ItemRepository $items): View
{
    $categoryUuids = $this->category->flattenChilds()->pluck('uuid');
    $query = Item::query()->whereIn('items.category_uuid', $categoryUuids);

    return view('catalogue.index', [
        'items' => $items->catalogueList($query, perPage: 24),
        'category' => $this->category,
    ]);
}
```

---

### 6. Экспорт прайсов: очередь + chunkById + streaming

**Что изменить:** `app/Http/Controllers/Price/Index.php`, новый Job `app/Jobs/BuildPriceExport.php`.

```php
// Запуск через очередь:
public function requestYmlExport(Request $request): JsonResponse
{
    $export = PriceExport::query()->create([
        'user_id' => $request->user()?->id,
        'status' => 'queued',
        'filters' => $request->only(['category_uuids', 'price_type_uuid']),
    ]);
    BuildPriceExport::dispatch($export->id)->onQueue('exports');
    return response()->json(['id' => $export->id, 'status_url' => route('price.exports.show', $export)], 202);
}

// Простой вариант без очереди — streaming:
return response()->streamDownload(function () use ($query) {
    echo "<?xml version=\"1.0\" encoding=\"UTF-8\"?>\n<yml_catalog>\n<shop>\n<offers>\n";
    $query->select(['items.id', 'items.uuid'])->availableForPrice()->orderBy('items.id')
        ->chunkById(500, function ($rows) {
            $items = ItemRepository::price(Item::query()->whereIn('items.uuid', $rows->pluck('uuid')))->get();
            foreach (ItemRepository::clarificationPriceGroups($items) as $item) {
                echo view('price.partials.offer', ['item' => $item])->render();
            }
        }, column: 'items.id');
    echo "\n</offers>\n</shop>\n</yml_catalog>\n";
}, 'price.yml', ['Content-Type' => 'application/xml; charset=UTF-8']);
```

---

### 7. Убрать `dd()` из production-кода и ограничить debug-инструменты

**Что изменить:** `HomeController.php`, `app/Models/Model.php`, `Pipes_/Price/ToCurrency.php`, `Livewire/Cart/Item/Delete.php`, service providers.

```php
// Было:
dd($someVar);

// Стало: удалить строку или заменить на logging:
Log::debug('var', ['value' => $someVar]);
```

```php
// AppServiceProvider.php или отдельный DebugServiceProvider:
if ($this->app->environment('local')) {
    $this->app->register(\Barryvdh\Debugbar\ServiceProvider::class);
    $this->app->register(\Laravel\Telescope\TelescopeServiceProvider::class);
}
```

---

### 8. Vite: отдельные entrypoints

**Что изменить:** создать `vite.config.js`, обновить Blade-layouts.

```js
// vite.config.js
import { defineConfig } from 'vite';
import laravel from 'laravel-vite-plugin';

export default defineConfig({
  plugins: [
    laravel({
      input: {
        public: 'resources/js/public.js',
        publicStyles: 'resources/scss/public.scss',
        private: 'resources/js/private.js',
        privateStyles: 'resources/scss/private.scss',
        catalogue: 'resources/js/catalogue.js',
        admin: 'resources/js/admin.js',
      },
      refresh: true,
    }),
  ],
  build: {
    manifest: true,
    sourcemap: false,
    rollupOptions: {
      output: {
        manualChunks: { vendor: ['axios'], ui: ['@fancyapps/ui'] },
      },
    },
  },
});
```

```blade
{{-- resources/views/layouts/open.blade.php --}}
@vite(['resources/scss/public.scss', 'resources/js/public.js'])
@stack('page-assets')

{{-- pages/catalogue/index.blade.php --}}
@push('page-assets')
    @vite(['resources/js/catalogue.js'])
@endpush
```

```bash
npm ci && npm run build
php artisan view:clear
```

---

### 9. Nginx: gzip/brotli, immutable cache для hashed assets

**Что изменить:** production nginx site config.

```nginx
gzip on;
gzip_comp_level 5;
gzip_min_length 1024;
gzip_types text/plain text/css text/xml application/json application/javascript image/svg+xml;

brotli on;
brotli_comp_level 5;
brotli_types text/plain text/css application/json application/javascript image/svg+xml;

keepalive_timeout 65;
http2 on;

location ~* ^/build/.+\.(js|css|woff2?|png|jpe?g|webp|avif|svg)$ {
    add_header Cache-Control "public, max-age=31536000, immutable" always;
    add_header Vary "Accept-Encoding" always;
    try_files $uri =404;
}

location ~* \.(png|jpe?g|gif|webp|avif|svg|ico|woff2?)$ {
    add_header Cache-Control "public, max-age=2592000" always;
    add_header Vary "Accept-Encoding" always;
    try_files $uri =404;
}
```

---

### 10. Изображения: WebP/AVIF, lazy loading, правильные размеры

**Что изменить:** Blade-компоненты карточек товара, `resources/scss/_fonts.scss`.

```blade
{{-- Карточка товара в каталоге --}}
<picture>
    <source type="image/avif" srcset="{{ image_url($image, 320, 'avif') }} 320w, {{ image_url($image, 640, 'avif') }} 640w">
    <source type="image/webp" srcset="{{ image_url($image, 320, 'webp') }} 320w, {{ image_url($image, 640, 'webp') }} 640w">
    <img src="{{ image_url($image, 320, 'jpg') }}" width="320" height="320" loading="lazy" decoding="async" alt="{{ $item->name }}">
</picture>

{{-- LCP-изображение первой карточки: --}}
<img src="{{ image_url($heroImage, 640, 'webp') }}" width="640" height="640" fetchpriority="high" decoding="async" alt="{{ $heroItem->name }}">
```

```scss
// resources/scss/_fonts.scss
@font-face {
  font-family: 'Inter';
  src: url('/fonts/inter-cyrillic-400.woff2') format('woff2');
  font-weight: 400;
  font-style: normal;
  font-display: swap;
}
@font-face {
  font-family: 'Inter';
  src: url('/fonts/inter-cyrillic-600.woff2') format('woff2');
  font-weight: 600;
  font-style: normal;
  font-display: swap;
}
```

---

### 11. Главная страница: `count()` на стороне SQL

**Что изменить:** `app/Http/Controllers/HomeController.php::index()`.

```php
// Было:
$newItemsCount = Item::query()->where('created_at', '>=', now()->subDays(30))->get(['id'])->count();

// Стало:
$newItemsCount = Item::query()->where('created_at', '>=', now()->subDays(30))->available()->count();

$reviews = Review::query()
    ->select(['id', 'profile_id', 'rating', 'text', 'created_at'])
    ->where('is_published', true)
    ->latest()->limit(12)->get();

$receipts = Receipt::query()
    ->select(['id', 'name', 'image', 'created_at'])
    ->latest()->limit(12)->get();
```

---

### 12. Кеш карточек каталога (Redis required)

**Что изменить:** новый `app/Repositories/ItemCardRepository.php`, инвалидация после импорта из 1C.

```php
final class ItemCardRepository
{
    public function getForSegment(string $itemUuid, string $segmentUuid): array
    {
        return Cache::tags(['item-cards', "item:{$itemUuid}", "segment:{$segmentUuid}"])
            ->remember("item-card:{$itemUuid}:segment:{$segmentUuid}", now()->addMinutes(30),
                fn () => $this->buildCard($itemUuid, $segmentUuid));
    }

    public function forgetItem(string $itemUuid): void
    {
        Cache::tags(["item:{$itemUuid}"])->flush();
    }

    private function buildCard(string $itemUuid, string $segmentUuid): array
    {
        $item = Item::query()
            ->select(['id', 'uuid', 'id_1c', 'name', 'category_uuid', 'brand_uuid'])
            ->with(['brand', 'images'])
            ->where('uuid', $itemUuid)
            ->firstOrFail();

        return ItemCardData::fromItem($item, $segmentUuid)->toArray();
    }
}
```

---

## Оценка потенциальной эффективности

| # | Мера | Ожидаемый эффект | Метрики | Приоритет | Сложность | Риски |
|---|------|-----------------|---------|-----------|-----------|-------|
| 1 | Production env + Redis cache/session + artisan optimize | TTFB −20–40%, CPU −15–30% | TTFB, CPU, disk I/O | 🔴 высокий | 🟢 низкая | Нужно убедиться, что config не зависит от runtime .env после config:cache |
| 2 | Остановить запись `pending` cookie consent в БД | TTFB на публичных страницах −10–25%, DB writes −50–70% | TTFB, DB QPS, DB writes, lock waits | 🔴 высокий | 🟡 средняя | Сохранить юридически значимый аудит фактических согласий |
| 3 | Индексы cookie_consents + items + categories + sales | Запросы каталога −30–60% по rows examined | Query time, rows examined, DB CPU | 🔴 высокий | 🟢 низкая | Индексы замедляют массовый импорт; проверить EXPLAIN на staging |
| 4 | Поиск: FULLTEXT вместо LIKE | Ускорение search endpoint в 3–10 раз | Search TTFB, rows examined | 🔴 высокий | 🟢 низкая | FULLTEXT в MySQL имеет особенности морфологии; проверить релевантность |
| 5 | Разделить list/detail в ItemRepository | Каталог ускоряется в 2–5 раз на тяжёлых категориях | Catalogue TTFB, memory, p95 | 🔴 высокий | 🟡 средняя | Аудит Blade-компонентов: не потерять нужные поля в list-view |
| 6 | Убрать `dd()` из production, ограничить Debugbar/Telescope | Availability +99.9% (нет случайных остановок), TTFB −5–10% | Availability, TTFB, error rate | 🔴 высокий | 🟢 низкая | Убедиться, что dev-инструменты доступны только в local/admin |
| 7 | Vite entrypoints + production build | FCP/LCP −20–35%, JS/CSS payload −40–60% | FCP, LCP, TTI, bytes | 🔴 высокий | 🟡 средняя | Страницы, рассчитывающие на глобальные скрипты, могут сломаться |
| 8 | Nginx gzip/brotli + cache headers + HTTP/2 | FCP −15–25%, LCP −10–20%, cache hit rate +50–80% для повторных визитов | FCP, LCP, cache hit rate | 🔴 высокий | 🟢 низкая | Синхронизировать с Vite hash naming |
| 9 | Кеш карточек (ItemCardRepository + Redis tags) | Каталог −40–70% нагрузки на DB при прогретом кеше | DB CPU, TTFB, p95/p99 | 🟡 средний | 🔴 высокая | Корректное инвалидирование после обмена с 1C |
| 10 | Экспорт прайсов: queue + chunkById | Memory peak −80–95%, HTTP worker освобождается мгновенно | Memory, request duration, worker availability | 🟡 средний | 🔴 высокая | Нужны stateful PriceExport модель и статус-endpoint для пользователя |
| 11 | Изображения: WebP/AVIF, lazy, fetchpriority, size attrs | LCP −15–30%, CLS →0, bytes −30–50% | LCP, CLS, bytes | 🟡 средний | 🟡 средняя | Проверить качество карточек, нужен image processing pipeline |
| 12 | Шрифты: WOFF2, subset, font-display: swap | FCP −5–15%, LCP −5–10%, bytes −60–80% | FCP, LCP, CLS, bytes | 🟡 средний | 🟢 низкая | Проверить соответствие фирменному стилю |
| 13 | HomeController: count() на стороне SQL, LIMIT | TTFB главной −10–20%, DB rows examined −90% для count-запросов | TTFB, DB QPS | 🟡 средний | 🟢 низкая | Минимальный риск |
| 14 | APM + MySQL slow query log | Observability: найти реальные p95/p99 bottlenecks | p95/p99 latency, MTTR | 🟢 низкий | 🟡 средняя | Ограничить sampling, чтобы мониторинг сам не стал нагрузкой |

---

## Порядок внедрения (Quick Wins → глубокие изменения)

### Шаг 1 — Quick wins (1–2 часа, наибольший ROI)

1. **Production env + artisan optimize:** `APP_DEBUG=false`, `LOG_LEVEL=warning`, Redis для cache/session/queue, OPcache, затем `php artisan optimize`, `config:cache`, `route:cache`, `view:cache`.
2. **Убрать все `dd()`** из production-файлов и ограничить Debugbar/Telescope переменной окружения.
3. **Nginx:** добавить gzip/brotli, immutable cache headers для `/build/` и cache headers для images/fonts.

### Шаг 2 — Индексы и поиск (2–4 часа)

4. Добавить миграцию индексов: `cookie_consents(status, date)`, `items(id_1c)`, `items(vendor_code)`, `items(barcode)`, `categories(parent_uuid, is_hide, default_sort)`, `sales(uuid_contractor, id)`. Проверить `EXPLAIN` на staging.
5. Перевести быстрый поиск с `LIKE '%...%'` на `whereFullText` + exact lookup по `id_1c`, `vendor_code`, `barcode`.
6. В `HomeController` заменить `get()->count()` на `count()`, добавить `LIMIT` для отзывов и receipts.

### Шаг 3 — Cookie consent и каталог (4–8 часов)

7. Остановить запись `pending` в `cookie_consents`; запустить cleanup-команду для старых pending-строк.
8. Разделить `ItemRepository::catalogue()` на `catalogueList()` и `catalogueDetail()`.
9. Перейти на SQL pagination в каталоге вместо `get()->groupBy()` на PHP.

### Шаг 4 — Vite, фронтенд, ассеты (4–8 часов)

10. Создать `vite.config.js`, настроить отдельные entrypoints, запустить production build.
11. Разделить SCSS: не подключать одновременно `public.scss` + `private.scss` + `app.scss`.
12. Оптимизировать шрифты: WOFF2, subset, `font-display: swap`.
13. Добавить `<picture>` с WebP/AVIF, `loading="lazy"`, `fetchpriority="high"` для LCP-изображения.

### Шаг 5 — Экспорт и глубокая оптимизация (8–16 часов)

14. Перенести генерацию YML/Excel в queue job с `chunkById(500)` или `response()->streamDownload`.
15. Добавить `ItemCardRepository` с кешем на Redis tags; настроить инвалидацию после импорта из 1C.
16. Снять after-baseline: Lighthouse/WebPageTest для главной, каталога, поиска, карточки товара; сравнить p95/p99 TTFB, FCP, LCP, TTI, rows examined, DB CPU, memory peak.

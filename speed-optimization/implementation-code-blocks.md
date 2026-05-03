# Блоки кода для оптимизации скорости

Документ дополняет `optimization-report.md` и показывает, где именно в Laravel/MySQL-проекте из issue #127 менять код. Сниппеты нужно адаптировать под реальные namespace, имена моделей и текущую схему БД перед применением в проекте.

## 1. Production env, cache, sessions, queues

Где: `.env.production`, серверный deploy script, `config/cache.php`, `config/session.php`, `config/queue.php`.

Цель: убрать debug overhead, file I/O для cache/session и синхронные очереди.

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

Проверка:

```bash
php artisan about
php artisan config:show app.debug
php artisan queue:work redis --once --verbose
redis-cli -n 1 DBSIZE
```

## 2. Cookie consent без записи Pending на каждый визит

Где: `app/Objects/CookieConsentManager.php`, модель `CookieConsent`, миграции `database/migrations`, `app/Console/Commands/PruneCookieConsents.php`.

Цель: не создавать строки `Pending` до действия пользователя. Pending хранится только в encrypted/httpOnly cookie, в БД пишутся только `Accepted`/`Rejected`.

### 2.1. Индексы и поля для обслуживания таблицы

Где: `database/migrations/2026_04_30_000001_optimize_cookie_consents.php`.

```php
<?php

use Illuminate\Database\Migrations\Migration;
use Illuminate\Database\Schema\Blueprint;
use Illuminate\Support\Facades\Schema;

return new class extends Migration {
    public function up(): void
    {
        Schema::table('cookie_consents', function (Blueprint $table) {
            $table->index(['status', 'date'], 'cookie_consents_status_date_idx');
            $table->index(['identifier', 'status'], 'cookie_consents_identifier_status_idx');
        });
    }

    public function down(): void
    {
        Schema::table('cookie_consents', function (Blueprint $table) {
            $table->dropIndex('cookie_consents_status_date_idx');
            $table->dropIndex('cookie_consents_identifier_status_idx');
        });
    }
};
```

### 2.2. Менеджер согласий

Где: `app/Objects/CookieConsentManager.php`.

```php
<?php

namespace App\Objects;

use App\Models\CookieConsent;
use Illuminate\Http\Request;
use Illuminate\Support\Facades\Cookie;
use Illuminate\Support\Str;

final class CookieConsentManager
{
    private const PENDING_COOKIE = 'cookie_consent_pending_id';
    private const DECISION_COOKIE = 'cookie_consent_id';

    public function state(Request $request): array
    {
        $decisionId = $request->cookie(self::DECISION_COOKIE);

        if ($decisionId) {
            $consent = CookieConsent::query()
                ->select(['id', 'identifier', 'status', 'date'])
                ->where('identifier', $decisionId)
                ->whereIn('status', ['Accepted', 'Rejected'])
                ->latest('date')
                ->first();

            if ($consent) {
                return ['status' => $consent->status, 'identifier' => $consent->identifier];
            }

            // Cookie есть, но запись в БД не найдена (очищена или невалидна).
            // Считаем решение устаревшим и возвращаем Pending без записи в БД.
        }

        return [
            'status' => 'Pending',
            'identifier' => $request->cookie(self::PENDING_COOKIE) ?: (string) Str::uuid(),
        ];
    }

    public function rememberPendingCookie(string $identifier): \Symfony\Component\HttpFoundation\Cookie
    {
        // TTL 7 дней совпадает с --pending-days в PruneCookieConsents, чтобы не хранить cookie дольше, чем запись в БД
        return Cookie::make(self::PENDING_COOKIE, $identifier, minutes: 60 * 24 * 7, secure: true, httpOnly: true, sameSite: 'lax');
    }

    public function accept(Request $request): CookieConsent
    {
        return $this->storeDecision($request, 'Accepted');
    }

    public function reject(Request $request): CookieConsent
    {
        return $this->storeDecision($request, 'Rejected');
    }

    private function storeDecision(Request $request, string $status): CookieConsent
    {
        $identifier = $request->cookie(self::PENDING_COOKIE) ?: (string) Str::uuid();

        return CookieConsent::query()->updateOrCreate(
            ['identifier' => $identifier],
            [
                'status' => $status,
                'date' => now(),
                'ip' => $request->ip(),
                'user_agent' => substr((string) $request->userAgent(), 0, 512),
            ],
        );
    }
}
```

### 2.3. Контроллер решения пользователя

Где: `app/Http/Controllers/CookieConsentController.php`.

```php
public function accept(Request $request, CookieConsentManager $manager): JsonResponse
{
    $consent = $manager->accept($request);

    return response()
        ->json(['status' => $consent->status])
        ->withoutCookie('cookie_consent_pending_id')
        ->withCookie(cookie('cookie_consent_id', $consent->identifier, 60 * 24 * 365, secure: true, httpOnly: true, sameSite: 'lax'));
}

public function reject(Request $request, CookieConsentManager $manager): JsonResponse
{
    $consent = $manager->reject($request);

    return response()
        ->json(['status' => $consent->status])
        ->withoutCookie('cookie_consent_pending_id')
        ->withCookie(cookie('cookie_consent_id', $consent->identifier, 60 * 24 * 365, secure: true, httpOnly: true, sameSite: 'lax'));
}
```

### 2.4. Cleanup старых записей

Где: `app/Console/Commands/PruneCookieConsents.php`.

```php
<?php

namespace App\Console\Commands;

use App\Models\CookieConsent;
use Illuminate\Console\Command;

final class PruneCookieConsents extends Command
{
    protected $signature = 'cookie-consents:prune {--pending-days=7} {--rejected-days=180}';
    protected $description = 'Remove stale cookie consent rows that are no longer useful for audit.';

    public function handle(): int
    {
        $pending = CookieConsent::query()
            ->where('status', 'Pending')
            ->where('date', '<', now()->subDays((int) $this->option('pending-days')))
            ->delete();

        $rejected = CookieConsent::query()
            ->where('status', 'Rejected')
            ->where('date', '<', now()->subDays((int) $this->option('rejected-days')))
            ->delete();

        $this->info("Deleted pending={$pending}, rejected={$rejected}");

        return self::SUCCESS;
    }
}
```

Где: `app/Console/Kernel.php`.

```php
protected function schedule(Schedule $schedule): void
{
    $schedule->command('cookie-consents:prune --pending-days=7 --rejected-days=180')
        ->dailyAt('03:20')
        ->withoutOverlapping();
}
```

## 3. Индексы для каталога, поиска и истории продаж

Где: `database/migrations/2026_04_30_000002_add_performance_indexes.php`.

Цель: ускорить частые фильтры и убрать full scan на `items`, `categories`, `sales`.

```sql
ALTER TABLE items
    ADD INDEX idx_items_category_archive_type (category_id_1c, in_archive, type),
    ADD INDEX idx_items_id_1c (id_1c),
    ADD INDEX idx_items_vendor_code (vendor_code),
    ADD INDEX idx_items_barcode (barcode),
    ADD FULLTEXT INDEX ft_items_name_synonyms (name, synonyms);

ALTER TABLE categories
    ADD INDEX idx_categories_id_1c (id_1c),
    ADD INDEX idx_categories_parent_id_1c (parent_id_1c),
    ADD INDEX idx_categories_parent_hide_sort (parent_uuid, is_hide, default_sort);

ALTER TABLE sales
    ADD INDEX idx_sales_uuid_contractor_id (uuid_contractor, id);
```

Перед добавлением на production сначала проверить план без ANALYZE (ANALYZE выполняет запрос и создает нагрузку на таблицы с миллионами строк):

```sql
EXPLAIN
SELECT id, name, price
FROM items
WHERE category_id_1c = 'CAT-001'
  AND in_archive = 0
  AND type = 'item'
ORDER BY name
LIMIT 40;

EXPLAIN
SELECT id, name
FROM items
WHERE MATCH(name, synonyms) AGAINST('+масло*' IN BOOLEAN MODE)
LIMIT 10;
```

После добавления индексов на staging можно использовать `EXPLAIN ANALYZE` для точных измерений:

```sql
EXPLAIN ANALYZE
SELECT id, name, price
FROM items
WHERE category_id_1c = 'CAT-001'
  AND in_archive = 0
  AND type = 'item'
ORDER BY name
LIMIT 40;
```

## 4. Каталог: list-view отдельно от detail-view

Где: `app/Repositories/ItemRepository.php`, контроллер каталога.

Цель: список каталога получает только поля карточки, а тяжелые аналоги/гайды/характеристики загружаются только на странице товара.

```php
public function catalogueList(CatalogueFilters $filters): LengthAwarePaginator
{
    return Item::query()
        ->select([
            'id',
            'id_1c',
            'category_id_1c',
            'name',
            'slug',
            'vendor_code',
            'barcode',
            'brand_id',
            'in_archive',
            'updated_at',
        ])
        ->where('type', 'item')
        ->where('in_archive', false)
        ->when($filters->categoryId1c, fn ($query, $categoryId) => $query->where('category_id_1c', $categoryId))
        ->with([
            'brand:id,name',
            'firstImage:id,item_id,path,width,height',
            'activePrice:id,item_id,price,old_price,price_type_id',
            'availableAmount:id,item_id,amount',
        ])
        ->orderBy($filters->sortColumn(), $filters->sortDirection())
        ->paginate($filters->perPage(), ['*'], 'page', $filters->page());
}
```

```php
public function catalogueDetail(string $slug): Item
{
    return Item::query()
        ->where('slug', $slug)
        ->with([
            'brand',
            'images',
            'attributes.attributeGroup',
            'characteristics',
            'analogues.firstImage',
            'guides',
            'segments',
            'activePrice',
            'availableAmount',
        ])
        ->firstOrFail();
}
```

Где: `app/Http/Controllers/Catalogue/Queries/Catalogue.php`.

```php
public function __invoke(CatalogueRequest $request, ItemRepository $items): View
{
    $filters = CatalogueFilters::fromRequest($request);

    return view('catalogue.index', [
        'items' => $items->catalogueList($filters),
        'filters' => $filters,
    ]);
}
```

## 5. Поиск: FULLTEXT, точные коды, без get()->count()

Где: `app/Http/Controllers/Search/FastSearch.php`.

Цель: заменить `LIKE '%term%'` для названий на `whereFullText`, а артикул/штрихкод искать exact/prefix по индексам.

```php
public function __invoke(Request $request): JsonResponse
{
    $term = trim((string) $request->query('q', ''));

    if (mb_strlen($term) < 2) {
        return response()->json(['items' => []]);
    }

    $booleanTerm = collect(preg_split('/\s+/u', $term))
        ->filter()
        ->map(fn (string $word) => '+' . $word . '*')
        ->implode(' ');

    $items = Item::query()
        ->select(['id', 'name', 'slug', 'vendor_code', 'barcode'])
        ->where('type', 'item')
        ->where('in_archive', false)
        ->where(function ($query) use ($term, $booleanTerm) {
            $query
                ->where('vendor_code', $term)
                ->orWhere('barcode', $term)
                ->orWhere('id_1c', $term)
                ->orWhereFullText(['name', 'synonyms'], $booleanTerm, ['mode' => 'boolean']);
        })
        ->orderByRaw(
            "CASE WHEN vendor_code = ? OR barcode = ? OR id_1c = ? THEN 0 ELSE 1 END",
            [$term, $term, $term],
        )
        ->limit(10)
        ->get();

    return response()->json(['items' => FastSearchResource::collection($items)]);
}
```

Где: `app/Http/Controllers/HomeController.php`.

```php
$booleanTerm = collect(preg_split('/\s+/u', $term))
    ->filter()
    ->map(fn (string $word) => '+' . $word . '*')
    ->implode(' ');

$baseQuery = Item::query()
    ->where('type', 'item')
    ->where(function ($query) use ($booleanTerm, $term) {
        $query
            ->whereFullText(['name', 'synonyms'], $booleanTerm, ['mode' => 'boolean'])
            ->orWhere('vendor_code', $term)
            ->orWhere('barcode', $term)
            ->orWhere('id_1c', $term);
    });

$availableCount = (clone $baseQuery)->where('in_archive', false)->whereHas('availableAmount')->count();
$archivedCount = (clone $baseQuery)->where('in_archive', true)->count();

$items = (clone $baseQuery)
    ->where('in_archive', false)
    ->with(['firstImage', 'activePrice', 'availableAmount'])
    ->paginate(24);
```

## 6. Экспорт прайсов: chunk, queue, streaming

Где: `app/Http/Controllers/Price/Index.php`, `app/Jobs/BuildPriceExport.php`, `app/Http/Controllers/Price/Base.php`.

Цель: не держать все товары и весь файл в памяти одного HTTP-запроса.

### 6.1. Запуск тяжелой генерации через очередь

```php
public function requestYmlExport(Request $request): JsonResponse
{
    $export = PriceExport::query()->create([
        'user_id' => $request->user()?->id,
        'status' => 'queued',
        'filters' => $request->only(['category_ids', 'price_type_id']),
    ]);

    BuildPriceExport::dispatch($export->id)->onQueue('exports');

    return response()->json([
        'id' => $export->id,
        'status_url' => route('price.exports.show', $export),
    ], 202);
}
```

### 6.2. Job с chunkById

```php
<?php

namespace App\Jobs;

use App\Models\Item;
use App\Models\PriceExport;
use Illuminate\Bus\Queueable;
use Illuminate\Contracts\Queue\ShouldQueue;
use Illuminate\Foundation\Bus\Dispatchable;
use Illuminate\Queue\InteractsWithQueue;
use Illuminate\Queue\SerializesModels;
use Illuminate\Support\Facades\Storage;

final class BuildPriceExport implements ShouldQueue
{
    use Dispatchable, InteractsWithQueue, Queueable, SerializesModels;

    public function __construct(private int $exportId) {}

    public function handle(): void
    {
        $export = PriceExport::query()->findOrFail($this->exportId);
        $path = "exports/price-{$export->id}.yml";

        Storage::put($path, "<?xml version=\"1.0\" encoding=\"UTF-8\"?>\n<yml_catalog>\n<shop>\n<offers>\n");

        Item::query()
            ->select(['id', 'name', 'slug', 'brand_id', 'category_id_1c', 'in_archive'])
            ->where('type', 'item')
            ->where(function ($query) {
                $query->where('in_archive', false)
                    ->orWhere(fn ($nested) => $nested->where('in_archive', true)->where('export_archived', true));
            })
            ->with(['brand:id,name', 'activePrice:id,item_id,price', 'category:id,id_1c,name'])
            ->chunkById(500, function ($items) use ($path) {
                $chunk = $items->map(fn (Item $item) => $this->renderOffer($item))->implode("\n");
                Storage::append($path, $chunk);
            });

        Storage::append($path, "\n</offers>\n</shop>\n</yml_catalog>\n");

        $export->update(['status' => 'ready', 'path' => $path, 'finished_at' => now()]);
    }

    private function renderOffer(Item $item): string
    {
        // Реализовать в соответствии со схемой YML и текущим Blade-шаблоном
        return "<offer id=\"{$item->id}\"><name>{$item->name}</name></offer>";
    }
}
```

### 6.3. Streaming download для готового файла

```php
public function download(PriceExport $export): StreamedResponse
{
    abort_unless($export->status === 'ready', 404);

    return Storage::download(
        $export->path,
        "price-{$export->id}.yml",
        ['Content-Type' => 'application/xml; charset=UTF-8'],
    );
}
```

Для простого экспорта без фоновой задачи:

```php
return response()->streamDownload(function () use ($query) {
    echo "<?xml version=\"1.0\" encoding=\"UTF-8\"?>\n<yml_catalog>\n<shop>\n<offers>\n";

    $query->chunkById(500, function ($items) {
        foreach ($items as $item) {
            echo view('price.partials.offer', ['item' => $item])->render();
        }
    });

    echo "\n</offers>\n</shop>\n</yml_catalog>\n";
}, 'price.yml', ['Content-Type' => 'application/xml; charset=UTF-8']);
```

## 7. Убрать лишние get()->count() и полные выборки на главной

Где: `app/Http/Controllers/HomeController.php`.

Цель: считать на стороне SQL и ограничивать данные, которые реально нужны на странице.

```php
$newItemsCount = Item::query()
    ->where('type', 'item')
    ->where('created_at', '>=', now()->subDays(30))
    ->count();

$reviews = Review::query()
    ->select(['id', 'user_id', 'rating', 'body', 'created_at'])
    ->where('is_published', true)
    ->latest()
    ->limit(12)
    ->get();

$receipts = Receipt::query()
    ->select(['id', 'title', 'image_path', 'created_at'])
    ->latest()
    ->limit(12)
    ->get();
```

## 8. Vite: отдельные entrypoints вместо общего тяжелого bundle

Где: `vite.config.js`, `resources/views/layouts/*.blade.php`.

Цель: публичные страницы не должны грузить private/admin JS и CSS.

```js
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
        manualChunks: {
          vendor: ['axios'],
          ui: ['@fancyapps/ui'],
        },
      },
    },
  },
});
```

Где: `resources/views/layouts/open.blade.php`.

```blade
@vite(['resources/scss/public.scss', 'resources/js/public.js'])

@stack('page-assets')
```

Где: страница каталога.

```blade
@push('page-assets')
    @vite(['resources/js/catalogue.js'])
@endpush
```

Проверка:

```bash
npm ci
npm run build
php artisan view:clear
```

## 9. Nginx/Apache cache headers, gzip/brotli, keep-alive

Где: production nginx site config или `public/.htaccess`, если используется Apache.

Цель: hashed assets получают долгий immutable cache, HTML и API не кэшируются случайно.

```nginx
gzip on;
gzip_comp_level 5;
gzip_min_length 1024;
gzip_types text/plain text/css text/xml application/json application/javascript application/xml+rss image/svg+xml;

brotli on;
brotli_comp_level 5;
brotli_types text/plain text/css application/json application/javascript image/svg+xml;

keepalive_timeout 65;
http2 on;

location ~* ^/build/.+\.(?:js|css|woff2?|png|jpe?g|webp|avif|svg)$ {
    add_header Cache-Control "public, max-age=31536000, immutable" always;
    add_header Vary "Accept-Encoding" always;
    try_files $uri =404;
}

location ~* \.(?:png|jpe?g|gif|webp|avif|svg|ico|woff2?)$ {
    add_header Cache-Control "public, max-age=2592000" always;
    add_header Vary "Accept-Encoding" always;
    try_files $uri =404;
}

location ~* \.(?:html)$ {
    add_header Cache-Control "no-cache" always;
}
```

Проверка:

```bash
curl -I https://example.com/build/assets/app.js
curl -H 'Accept-Encoding: br' -I https://example.com/
```

## 10. Изображения и шрифты

Где: Blade-компоненты карточек товара, `resources/scss/_fonts.scss`, pipeline генерации медиа.

Цель: уменьшить LCP и убрать CLS.

```blade
<picture>
    <source
        type="image/avif"
        srcset="{{ image_url($item->firstImage, 320, 'avif') }} 320w, {{ image_url($item->firstImage, 640, 'avif') }} 640w"
    >
    <source
        type="image/webp"
        srcset="{{ image_url($item->firstImage, 320, 'webp') }} 320w, {{ image_url($item->firstImage, 640, 'webp') }} 640w"
    >
    <img
        src="{{ image_url($item->firstImage, 320, 'jpg') }}"
        width="320"
        height="320"
        loading="lazy"
        decoding="async"
        alt="{{ $item->name }}"
    >
</picture>
```

Для LCP-изображения на первой карточке:

```blade
<img
    src="{{ image_url($heroItem->firstImage, 640, 'webp') }}"
    width="640"
    height="640"
    fetchpriority="high"
    decoding="async"
    alt="{{ $heroItem->name }}"
>
```

Шрифты:

```scss
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

## 11. Кэш карточек каталога

Где: `app/Repositories/ItemCardRepository.php`, invalidation после обмена с 1C.

Цель: не пересобирать цены, остатки, скидки и изображения на каждый запрос каталога. Требует Redis в качестве cache driver (поддерживает теги).

```php
final class ItemCardRepository
{
    public function getForSegment(int $itemId, string $segmentId): array
    {
        return Cache::tags(['item-cards', "item:{$itemId}", "segment:{$segmentId}"])
            ->remember(
                "item-card:{$itemId}:segment:{$segmentId}",
                now()->addMinutes(30),
                fn () => $this->buildCard($itemId, $segmentId),
            );
    }

    public function forgetItem(int $itemId): void
    {
        Cache::tags(["item:{$itemId}"])->flush();
    }

    private function buildCard(int $itemId, string $segmentId): array
    {
        $item = Item::query()
            ->select(['id', 'name', 'slug', 'brand_id'])
            ->with(['brand:id,name', 'firstImage:id,item_id,path', 'activePrice'])
            ->findOrFail($itemId);

        return ItemCardData::fromItem($item, $segmentId)->toArray();
    }
}
```

Инвалидация после импорта:

```php
ItemImported::dispatch($item->id);

Event::listen(ItemImported::class, function (ItemImported $event) {
    app(ItemCardRepository::class)->forgetItem($event->itemId);
});
```

## 12. Production-safe debug и аварийные dd()

Где: `app/Http/Controllers/HomeController.php`, `app/Models/Model.php`, service providers.

Цель: `dd()` не должен останавливать production-запросы, Debugbar/Telescope не должны грузиться в production.

```php
public function emailFeedback(EmailFeedbackRequest $request): RedirectResponse
{
    Mail::to(config('mail.feedback_to'))->queue(new FeedbackMail($request->validated()));

    return back()->with('status', __('feedback.sent'));
}
```

```php
if ($this->app->environment('local')) {
    $this->app->register(\Barryvdh\Debugbar\ServiceProvider::class);
    $this->app->register(\Laravel\Telescope\TelescopeServiceProvider::class);
}
```

## 13. Минимальные тесты для внедрения

Где: `tests/Feature`, `tests/Unit`.

Цель: зафиксировать, что изменения не возвращают старые проблемы.

```php
public function test_pending_cookie_consent_does_not_create_database_row(): void
{
    $this->get('/')->assertOk();

    $this->assertDatabaseCount('cookie_consents', 0);
}

public function test_accept_cookie_consent_creates_single_decision_row(): void
{
    $this->withCookie('cookie_consent_pending_id', 'test-id')
        ->postJson('/cookie-consent/accept')
        ->assertOk();

    $this->assertDatabaseHas('cookie_consents', [
        'identifier' => 'test-id',
        'status' => 'Accepted',
    ]);
}
```

```php
public function test_fast_search_uses_limited_payload(): void
{
    Item::factory()->create(['name' => 'Масло моторное', 'synonyms' => 'масло']);

    $this->getJson('/fast-search?q=масло')
        ->assertOk()
        ->assertJsonStructure(['items' => [['id', 'name', 'slug']]]);
}
```

## 14. Порядок внедрения

1. Снять baseline: Lighthouse/WebPageTest для главной, каталога, поиска и карточки товара; slow query log за 24 часа; p95/p99 TTFB.
2. Включить production env/cache/Redis и nginx cache headers.
3. Исправить cookie consent, удалить старые `Pending`, добавить индексы.
4. Перевести поиск на `whereFullText` и точные индексы.
5. Разделить list/detail запросы каталога.
6. Перенести экспорт прайсов в queue/chunk/streaming.
7. Разделить Vite entrypoints, оптимизировать fonts/images.
8. Повторить baseline и сравнить TTFB, FCP, LCP, TTI/INP, rows examined, DB CPU, memory peak.

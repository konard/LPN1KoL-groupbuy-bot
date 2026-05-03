# Блоки кода для оптимизации скорости

Документ дополняет `optimization-report.md` и показывает, где именно в Laravel/MySQL-проекте из issue #127/#155 менять код. Сниппеты привязаны к фактическому дампу `alfastok_db_1c8_8.sql`: cookie consent хранит `token`, товары связаны через `uuid`/`category_uuid`, цены и остатки лежат в `item_price`, `item_price_type`, `amount_item` по `item_uuid`. Перед внедрением каждый блок нужно прогнать на staging и сверить с текущими namespace проекта.

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

## 2. Cookie consent без записи pending на каждый визит

Где: `app/Objects/CookieConsentManager.php`, модель `CookieConsent`, миграции `database/migrations`, `app/Console/Commands/PruneCookieConsents.php`.

Цель: не создавать строки `pending` до действия пользователя. До выбора состояние живет только в cookie `cookie_consent_token`, в БД пишутся только фактические решения `accepted`/`rejected`.

### 2.1. Индексы и обслуживание таблицы

Где: `database/migrations/2026_05_03_000001_optimize_cookie_consents.php`.

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
            $table->index(['profile_id', 'status', 'date'], 'cookie_consents_profile_status_date_idx');
        });
    }

    public function down(): void
    {
        Schema::table('cookie_consents', function (Blueprint $table) {
            $table->dropIndex('cookie_consents_status_date_idx');
            $table->dropIndex('cookie_consents_profile_status_date_idx');
        });
    }
};
```

### 2.2. Менеджер согласий

Где: `app/Objects/CookieConsentManager.php`.

```php
<?php

namespace App\Objects;

use App\Enums\CookieConsents;
use App\Models\CookieConsent;
use Illuminate\Http\Request;
use Illuminate\Support\Facades\Cookie;
use Illuminate\Support\Str;

final class CookieConsentManager
{
    private const TOKEN_COOKIE = 'cookie_consent_token';

    public function state(Request $request): CookieConsents
    {
        $token = $this->token($request);

        $consent = CookieConsent::query()
            ->select(['id', 'token', 'status', 'date'])
            ->where('token', $token)
            ->whereIn('status', [
                CookieConsents::Accepted->value,
                CookieConsents::Rejected->value,
            ])
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

        Cookie::queue(cookie(
            self::TOKEN_COOKIE,
            $token,
            minutes: 60 * 24 * 365,
            secure: true,
            httpOnly: true,
            sameSite: 'lax',
        ));

        return $token;
    }

    private function storeDecision(Request $request, CookieConsents $status): CookieConsent
    {
        $token = $this->token($request);

        return CookieConsent::query()->updateOrCreate(
            ['token' => $token],
            [
                'profile_id' => profile()?->id,
                'ip' => $request->ip(),
                'session_id' => $request->session()->getId(),
                'status' => $status->value,
                'date' => now(),
            ],
        );
    }
}
```

### 2.3. Контроллеры решения пользователя

Где: `app/Http/Controllers/CookieConsent/Accept.php` и `app/Http/Controllers/CookieConsent/Reject.php`.

```php
public function __invoke(Request $request, CookieConsentManager $manager): JsonResponse
{
    $consent = $manager->accept($request);

    return response()->json([
        'status' => $consent->status->value,
    ]);
}
```

```php
public function __invoke(Request $request, CookieConsentManager $manager): JsonResponse
{
    $consent = $manager->reject($request);

    return response()->json([
        'status' => $consent->status->value,
    ]);
}
```

### 2.4. Cleanup старых записей

Где: `app/Console/Commands/PruneCookieConsents.php`.

```php
<?php

namespace App\Console\Commands;

use App\Enums\CookieConsents;
use App\Models\CookieConsent;
use Illuminate\Console\Command;

final class PruneCookieConsents extends Command
{
    protected $signature = 'cookie-consents:prune {--pending-days=7} {--rejected-days=180}';
    protected $description = 'Remove stale cookie consent rows outside the audit window.';

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

Где: `database/migrations/2026_05_03_000002_add_performance_indexes.php`.

Цель: ускорить частые фильтры и убрать full scan на `items`, `categories`, `sales`. FULLTEXT по `items(name, synonyms)` в дампе уже есть как `items_name_synonyms_fulltext`, поэтому повторно его не добавляем.

```sql
ALTER TABLE cookie_consents
    ADD INDEX cookie_consents_status_date_idx (status, date),
    ADD INDEX cookie_consents_profile_status_date_idx (profile_id, status, date);

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

Перед добавлением на production сначала проверить план без выполнения тяжелого запроса:

```sql
EXPLAIN
SELECT id, uuid, id_1c, name
FROM items
WHERE category_id_1c = '3149'
  AND type = 'product'
ORDER BY name
LIMIT 40;

EXPLAIN
SELECT id, uuid, id_1c, name
FROM items
WHERE MATCH(name, synonyms) AGAINST('+масло*' IN BOOLEAN MODE)
LIMIT 10;
```

После добавления индексов на staging можно использовать `EXPLAIN ANALYZE` для точных измерений:

```sql
EXPLAIN ANALYZE
SELECT id, uuid, id_1c, name
FROM items
WHERE category_id_1c = '3149'
  AND type = 'product'
ORDER BY name
LIMIT 40;
```

## 4. Каталог: list-view отдельно от detail-view

Где: `app/Repositories/ItemRepository.php`, `app/Http/Controllers/Catalogue/Queries/Catalogue.php`.

Цель: список каталога получает только поля карточки, а тяжелые аналоги/гайды/характеристики загружаются только на странице товара.

```php
use App\Models\Item;
use Illuminate\Contracts\Pagination\LengthAwarePaginator;
use Illuminate\Database\Eloquent\Builder;
use Illuminate\Support\Facades\DB;

final class ItemRepository
{
    public function catalogueList(Builder $query, int $perPage = 24): LengthAwarePaginator
    {
        return $query
            ->select([
                'items.id',
                'items.id_1c',
                'items.uuid',
                'items.category_uuid',
                'items.name',
                'items.vendor_code',
                'items.barcode',
                'items.brand_uuid',
                'items.price_group_uuid',
                'items.updated_at',
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
}
```

Detail-view должен оставаться отдельным:

```php
public function catalogueDetail(string $uuid): Item
{
    return Item::query()
        ->where('items.uuid', $uuid)
        ->with([
            'brand',
            'images',
            'attributes.attribute',
            'characteristics',
            'guides',
            'schemes',
            'segments',
        ])
        ->firstOrFail();
}
```

Где: `app/Http/Controllers/Catalogue/Queries/Catalogue.php`.

```php
public function __invoke(CatalogueRequest $request, ItemRepository $items): View
{
    $categoryUuids = $this->category
        ->flattenChilds()
        ->pluck('uuid');

    $query = Item::query()
        ->whereIn('items.category_uuid', $categoryUuids);

    return view('catalogue.index', [
        'items' => $items->catalogueList($query, perPage: 24),
        'category' => $this->category,
    ]);
}
```

## 5. Поиск: FULLTEXT, точные коды, без get()->count()

Где: `app/Http/Controllers/Search/FastSearch.php`.

Цель: заменить `LIKE '%term%'` для названий на `whereFullText`, а артикул/штрихкод/код 1C искать exact/prefix по индексам.

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
        ->select(['id', 'id_1c', 'uuid', 'name', 'vendor_code', 'barcode'])
        ->available()
        ->notCheap()
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
    ->where(function ($query) use ($booleanTerm, $term) {
        $query
            ->whereFullText(['name', 'synonyms'], $booleanTerm, ['mode' => 'boolean'])
            ->orWhere('vendor_code', $term)
            ->orWhere('barcode', $term)
            ->orWhere('id_1c', $term);
    });

$availableCount = (clone $baseQuery)
    ->whereExists(function ($query) {
        $query->selectRaw('1')
            ->from('amount_item')
            ->whereColumn('amount_item.item_uuid', 'items.uuid')
            ->where('amount_item.amount_id', 1)
            ->whereRaw('CAST(amount_item.value AS DECIMAL(12, 3)) > 0');
    })
    ->count();
$totalCount = (clone $baseQuery)->count();

$items = (clone $baseQuery)
    ->available()
    ->notCheap()
    ->orderBy('name')
    ->paginate(24);
```

## 6. Экспорт прайсов: chunk, queue, streaming

Где: `app/Http/Controllers/Price/Index.php`, `app/Http/Controllers/Price/Base.php`, `app/Jobs/BuildPriceExport.php`.

Цель: не держать все товары и весь файл в памяти одного HTTP-запроса. Старый `Price/Index.php` должен быть переведен на ту же схему доступности, что и `ItemRepository::price()`: `availableForPrice()`, `category_uuid`, `item_uuid`, `item_price_type`.

### 6.1. Запуск тяжелой генерации через очередь

```php
public function requestYmlExport(Request $request): JsonResponse
{
    $export = PriceExport::query()->create([
        'user_id' => $request->user()?->id,
        'status' => 'queued',
        'filters' => $request->only(['category_uuids', 'price_type_uuid']),
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
use App\Repositories\ItemRepository;
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
            ->select(['items.id', 'items.uuid'])
            ->availableForPrice()
            ->when(
                $export->filters['category_uuids'] ?? [],
                fn ($query, array $uuids) => $query->whereIn('items.category_uuid', $uuids),
            )
            ->orderBy('items.id')
            ->chunkById(500, function ($rows) use ($path) {
                $uuids = $rows->pluck('uuid');

                $items = ItemRepository::price(
                    Item::query()->whereIn('items.uuid', $uuids),
                )->get();

                $items = ItemRepository::clarificationPriceGroups($items);

                $chunk = $items
                    ->map(fn (Item $item) => $this->renderOffer($item))
                    ->implode("\n");

                Storage::append($path, $chunk);
            }, column: 'items.id');

        Storage::append($path, "\n</offers>\n</shop>\n</yml_catalog>\n");

        $export->update(['status' => 'ready', 'path' => $path, 'finished_at' => now()]);
    }

    private function renderOffer(Item $item): string
    {
        return view('price.partials.offer', ['item' => $item])->render();
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

    $query->select(['items.id', 'items.uuid'])
        ->availableForPrice()
        ->orderBy('items.id')
        ->chunkById(500, function ($rows) {
            $items = ItemRepository::price(
                Item::query()->whereIn('items.uuid', $rows->pluck('uuid')),
            )->get();

            foreach (ItemRepository::clarificationPriceGroups($items) as $item) {
                echo view('price.partials.offer', ['item' => $item])->render();
            }
        }, column: 'items.id');

    echo "\n</offers>\n</shop>\n</yml_catalog>\n";
}, 'price.yml', ['Content-Type' => 'application/xml; charset=UTF-8']);
```

## 7. Убрать лишние get()->count() и полные выборки на главной

Где: `app/Http/Controllers/HomeController.php`.

Цель: считать на стороне SQL и ограничивать данные, которые реально нужны на странице.

```php
$newItemsCount = Item::query()
    ->where('created_at', '>=', now()->subDays(30))
    ->available()
    ->count();

$reviews = Review::query()
    ->select(['id', 'profile_id', 'rating', 'text', 'created_at'])
    ->where('is_published', true)
    ->latest()
    ->limit(12)
    ->get();

$receipts = Receipt::query()
    ->select(['id', 'name', 'image', 'created_at'])
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

Цель: уменьшить LCP и убрать CLS. В дампе изображения лежат в `item_images` и связаны через `item_uuid`.

```blade
@php($image = $item->image ?: $item->images->first()?->image_sm)

<picture>
    <source
        type="image/avif"
        srcset="{{ image_url($image, 320, 'avif') }} 320w, {{ image_url($image, 640, 'avif') }} 640w"
    >
    <source
        type="image/webp"
        srcset="{{ image_url($image, 320, 'webp') }} 320w, {{ image_url($image, 640, 'webp') }} 640w"
    >
    <img
        src="{{ image_url($image, 320, 'jpg') }}"
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
    src="{{ image_url($heroImage, 640, 'webp') }}"
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

Цель: не пересобирать цены, остатки, скидки и изображения на каждый запрос каталога. Требует Redis в качестве cache driver, потому что нужны tags.

```php
final class ItemCardRepository
{
    public function getForSegment(string $itemUuid, string $segmentUuid): array
    {
        return Cache::tags(['item-cards', "item:{$itemUuid}", "segment:{$segmentUuid}"])
            ->remember(
                "item-card:{$itemUuid}:segment:{$segmentUuid}",
                now()->addMinutes(30),
                fn () => $this->buildCard($itemUuid, $segmentUuid),
            );
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

Инвалидация после импорта:

```php
ItemImported::dispatch($item->uuid);

Event::listen(ItemImported::class, function (ItemImported $event) {
    app(ItemCardRepository::class)->forgetItem($event->itemUuid);
});
```

## 12. Production-safe debug и аварийные dd()

Где: `app/Http/Controllers/HomeController.php`, `app/Models/Model.php`, `app/Objects/Pipes_/Price/ToCurrency.php`, `Livewire/Cart/Item/Delete.php`, service providers.

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
```

```php
public function test_accept_cookie_consent_creates_single_decision_row(): void
{
    $this->withCookie('cookie_consent_token', 'test-token')
        ->postJson('/cookie-consent/accept')
        ->assertOk();

    $this->assertDatabaseHas('cookie_consents', [
        'token' => 'test-token',
        'status' => 'accepted',
    ]);
}
```

```php
public function test_fast_search_uses_limited_payload(): void
{
    Item::factory()->create([
        'uuid' => (string) Str::uuid(),
        'name' => 'Масло моторное',
        'synonyms' => 'масло',
    ]);

    $this->getJson('/fast-search?q=масло')
        ->assertOk()
        ->assertJsonStructure(['items' => [['id', 'id_1c', 'uuid', 'name']]]);
}
```

## 14. Порядок внедрения

1. Снять baseline: Lighthouse/WebPageTest для главной, каталога, поиска и карточки товара; slow query log за 24 часа; p95/p99 TTFB.
2. Включить production env/cache/Redis и nginx cache headers.
3. Исправить cookie consent, удалить старые `pending`, добавить индексы.
4. Перевести поиск на `whereFullText` и точные индексы.
5. Разделить list/detail запросы каталога.
6. Перенести экспорт прайсов в queue/chunk/streaming.
7. Разделить Vite entrypoints, оптимизировать fonts/images.
8. Повторить baseline и сравнить TTFB, FCP, LCP, TTI/INP, rows examined, DB CPU, memory peak.

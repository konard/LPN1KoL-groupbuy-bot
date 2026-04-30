# Отчет по оптимизации скорости

## Контекст анализа

Анализ выполнен по архиву проекта `1c8_private-master.zip` и дампу `alfastok_db_1c8_8.sql` из предоставленной папки. Проект - Laravel 10/PHP 8.1+ с MySQL 8, Vite, Filament/Livewire и большим B2B-каталогом. Локальный импорт дампа в этой среде не запускался, потому что здесь нет MySQL/MariaDB/Docker; выводы по базе сделаны статически по DDL и данным дампа.

Ключевые размеры из дампа: 101 таблица, самые крупные таблицы - `cookie_consents` 2 168 684 строк, `item_price_type` 822 549, `sale_products` 334 131, `item_order` 219 739, `attribute_item` 115 603, `item_price` 95 243, `amount_item` 50 676, `items` 22 337.

## 1. Выявленные проблемы

| Проблема | Где обнаружено | Влияние |
| --- | --- | --- |
| На каждый визит создается или читается запись согласия cookies, даже пока пользователь ничего не выбрал | `app/Objects/CookieConsentManager.php`, таблица `cookie_consents` 2.17M строк, компонент cookie banner в layout | critical |
| Продакшен-настройки по умолчанию остаются dev-oriented: `APP_DEBUG=true`, `CACHE_DRIVER=file`, `SESSION_DRIVER=file`, `QUEUE_CONNECTION=sync`, `LOG_LEVEL=debug` | `.env.example`, `config/cache.php`, `config/session.php`, `config/queue.php`, `config/debugbar.php` | critical |
| Каталог собирает слишком тяжелую карточку товара: цены, остатки, скидки, аналоги, атрибуты, характеристики, гайды, изображения и сегменты в одном запросе | `app/Repositories/ItemRepository.php::catalogue()` | critical |
| Загрузка каталога получает все товары выбранных категорий через `get()` и группирует в PHP, вместо page/chunk/limit на уровне SQL | `app/Http/Controllers/Catalogue/Queries/Catalogue.php` | high |
| Быстрый поиск и основной поиск используют `LIKE '%слово%'`; существующий FULLTEXT по `items(name, synonyms)` не используется | `app/Http/Controllers/Search/FastSearch.php`, `HomeController::search()` | high |
| В поиске есть повторные `get()->count()`, несколько клонов почти одинаковых запросов и отдельные запросы по артикулу/штрихкоду с leading wildcard | `HomeController::search()` | high |
| Генерация YML/Excel прайса строит весь файл и весь набор товаров в памяти, делает N+1 по категориям, брендам, характеристикам и settings | `app/Http/Controllers/Price/Index.php`, `app/Http/Controllers/Price/Base.php` | high |
| В запросе YML не сгруппирован `orWhere`, поэтому условие архива может расширять выборку вне выбранных категорий | `Price/Index.php::generateYML()` | high |
| Нет `vite.config.*`, при этом Blade-шаблоны используют `@vite(...)`; сборка ассетов не воспроизводима и может ломать production cache-busting | корень проекта, `resources/views/layouts/*.blade.php` | high |
| Layout одновременно подключает `app.scss`, `private.scss`, `public.scss`; это повышает CSS payload и риск дублирования правил | `resources/views/layouts/app.blade.php`, `resources/views/layouts/open.blade.php` | medium |
| На публичных страницах подключаются старые тяжелые JS-модули глобально, включая `jquery-ui.min.js` 286 KB, inputmask 221 KB, fancybox 161 KB | `resources/js`, `resources/views/layouts/open.blade.php`, страницы каталога | medium |
| Фонты занимают 5.1 MB, есть SVG/TTF/EOT/OTF форматы и нет WOFF2-subset стратегии | `resources/fonts`, SCSS `@font-face` | medium |
| В `public/.htaccess` нет правил долгого кэширования статических файлов, gzip/brotli и image/font cache headers | `public/.htaccess`, отсутствуют nginx/apache production configs | medium |
| Главная страница делает лишние полные выборки: новые товары через `get(['id'])->count()`, все отзывы, receipts с `get()->unique()` | `HomeController::index()` | medium |
| В продакшен-коде есть активный `dd($request->all())`, а в базовой модели - аварийные `dd()` при отдельных casts | `HomeController::emailFeedback()`, `app/Models/Model.php` | medium |
| Для популярных фильтров и JOIN-полей не хватает прикладных индексов: `items.category_id_1c`, `items.id_1c`, `items.vendor_code`, `items.barcode`, `categories.id_1c`, `categories.parent_id_1c`, `sales.uuid_contractor` | DDL дампа и код репозиториев/контроллеров | high |
| File cache/file sessions при высокой посещаемости создают I/O contention и не дают нормального tag/cache-lock поведения | `config/cache.php`, `config/session.php`, `BaseCacheRepository.php` | high |
| Очереди синхронные, поэтому экспорт, письма, импорт/обработка изображений и внешние API могут блокировать HTTP-запрос | `config/queue.php`, контроллеры экспорта и отправки email | high |

## 2. План оптимизации

| Действие | Ожидаемый эффект | Затрагиваемые метрики | Приоритет | Риски |
| --- | --- | --- | --- | --- |
| Перевести production env на `APP_ENV=production`, `APP_DEBUG=false`, `LOG_LEVEL=warning`, Redis для cache/session/queue, включить OPcache и выполнить `config:cache`, `route:cache`, `view:cache`, `event:cache` | Убрать debug overhead, снизить disk I/O, ускорить bootstrap Laravel | TTFB, CPU, disk I/O, p95 latency | P0 | Нужна проверка, что config не зависит от runtime `.env` после `config:cache` |
| Переделать cookie consent: не создавать `Pending` в БД до действия пользователя, хранить pending в signed cookie, писать в БД только accept/reject, добавить TTL cleanup старых pending/rejected | Резко сократить запись/чтение самой большой таблицы на публичных страницах | TTFB, DB QPS, DB writes, lock waits | P0 | Нужно сохранить юридически значимый аудит фактических согласий |
| Добавить план обслуживания `cookie_consents`: удалить старые pending, добавить индекс по `date/status`, рассмотреть partition по месяцу | Уменьшить размер hot index и ускорить cleanup/analytics | DB size, index size, query time | P0 | Удаление данных согласовать с политикой хранения |
| Разделить `ItemRepository::catalogue()` на list-view и detail-view; для списка отдавать только id, name, price, amount, first image, badges | Сократить ширину SELECT и число JSON subselect/eager-load операций | Catalogue TTFB, DB CPU, memory, response size | P0 | Нужен аудит Blade-компонентов карточки, чтобы не потерять нужные поля |
| В каталоге заменить `get()->groupBy()` на SQL pagination/limit per category или ленивую загрузку категорий с отдельным endpoint | Не грузить тысячи товаров в PHP для одной страницы | TTFB, memory, p95/p99 latency | P0 | Может измениться порядок отображения и lazy-load UX |
| Создать материализованное представление/таблицу `item_cards` или кэш Redis для карточек каталога по сегменту клиента/ценовому соглашению | Убрать повторную сборку цен, остатков, скидок и JSON-агрегатов на каждом запросе | DB CPU, cache hit rate, TTFB | P1 | Нужно корректное инвалидирование после обмена с 1C |
| Перевести поиск на `MATCH(name, synonyms) AGAINST(...)` и точные/префиксные индексы для `id_1c`, `vendor_code`, `barcode` | Ускорить поиск и улучшить релевантность | Search TTFB, DB rows examined | P0 | FULLTEXT в MySQL имеет особенности морфологии; релевантность надо проверить на реальных запросах |
| В `HomeController::search()` заменить `get()->count()` на `count()`, объединить повторные запросы, убрать leading wildcard там, где возможен exact/prefix search | Уменьшить число запросов и объем данных, передаваемых в PHP | Search TTFB, DB QPS, memory | P1 | Нужно сохранить текущую логику групп "в наличии/нет/архив" |
| Переписать YML/Excel exports на `cursor()`/`chunkById()` и `response()->streamDownload()`, вынести тяжелую генерацию в queue job | Снизить memory peak и не держать HTTP worker до конца генерации | Memory, request duration, worker availability | P1 | Потребуется хранение временного файла и статус задачи для пользователя |
| Исправить N+1 в экспортах: заранее загрузить бренды/характеристики, использовать `$item->brand`, кэшировать `setting()` вне цикла, сгруппировать `orWhere` | Ускорить генерацию прайсов и убрать лишние SQL-запросы | DB QPS, export duration | P1 | Нужны regression tests на состав файла |
| Добавить недостающие индексы: `items(category_id_1c, in_archive, type)`, `items(id_1c)`, `items(vendor_code)`, `items(barcode)`, `categories(id_1c)`, `categories(parent_id_1c)`, `categories(parent_uuid, is_hide, default_sort)`, `sales(uuid_contractor, id)` | Ускорить частые фильтры, поиск по коду и построение дерева категорий/истории продаж | DB rows examined, query time, CPU | P1 | Индексы увеличат размер БД и замедлят массовый импорт, добавлять после EXPLAIN на production data |
| Восстановить `vite.config.js` и настроить отдельные entrypoints: public, private, catalogue, admin; подключать только нужные bundle на странице | Уменьшить JS/CSS payload и стабилизировать production build | FCP, LCP, TTI, transferred bytes | P0 | Нужна проверка всех страниц, где сейчас рассчитывают на глобальные скрипты |
| Разделить SCSS и удалить дубли: не подключать одновременно public/private/app там, где нужен один layout bundle | Уменьшить CSS bytes и время style recalculation | FCP, render blocking time, CSS size | P1 | Возможны визуальные регрессии из-за порядка CSS |
| Оптимизировать шрифты: WOFF2, subset кириллица/латиница, только нужные веса, `font-display: swap`, preload критичного шрифта | Снизить блокировку текста и объем загрузки | FCP, LCP, CLS, transferred bytes | P1 | Нужно проверить соответствие фирменному стилю |
| Настроить nginx/apache/CDN: gzip/brotli, immutable cache для hashed assets, cache headers для fonts/images, HTTP/2/3, CDN для `/storage` | Ускорить повторные заходы и загрузку медиа | LCP, FCP, cache hit rate, bytes from origin | P0 | Нужна синхронизация с Vite hash naming и политикой обновления storage-файлов |
| Добавить image pipeline: WebP/AVIF thumbnails, lazy loading, width/height, `fetchpriority=high` для LCP-изображений | Уменьшить вес каталога и убрать layout shift | LCP, CLS, transferred bytes | P1 | Нужно сохранить качество карточек товара |
| Убрать active `dd()` из production routes/models, закрыть Debugbar/Telescope/log-viewer от production traffic | Исключить аварийные остановки и лишний profiling overhead | Availability, TTFB, error rate | P0 | Нужна проверка, что dev-инструменты доступны только локально/admin |
| Ввести APM и slow query protocol: MySQL slow log, Performance Schema, Laravel Telescope только local, Blackfire/New Relic/Sentry tracing | Появятся реальные p95/p99 bottlenecks и можно приоритизировать по фактам | Observability, MTTR, p95/p99 latency | P1 | Нужно ограничить sampling, чтобы мониторинг сам не стал нагрузкой |

## 3. Ожидаемый общий результат

Без production-бенчмарков точные цифры нужно подтвердить через Lighthouse/WebPageTest/APM и slow query log, но по статическому анализу ожидаемый эффект высокий:

| Область | Ожидаемое улучшение |
| --- | --- |
| Публичные страницы с кэшем, отключенным debug и Redis cache/session | TTFB ниже на 20-50% |
| Каталог после разделения list/detail и кэша карточек | Ускорение серверной части в 2-5 раз на тяжелых категориях |
| Поиск после FULLTEXT и индексов | Ускорение endpoint в 3-10 раз на популярных запросах |
| Первый визит после оптимизации CSS/JS/fonts/images/cache headers | FCP/LCP лучше на 20-40%, меньше render-blocking ресурсов |
| Повторные визиты после immutable cache/CDN | Меньше обращений к origin на 50-80% для статики и медиа |
| Экспорт прайсов после streaming/queue/chunk | Стабильная память вместо роста пропорционально числу товаров, меньше занятых PHP workers |

Основные метрики, которые должны улучшиться: TTFB, LCP, FCP, TTI/INP, server p95/p99 latency, DB CPU, rows examined, QPS к MySQL, peak memory PHP workers, cache hit rate, размер JS/CSS/fonts/images на страницу.

## 4. Quick wins: 3-5 действий на 1-2 часа

1. Настроить production env и artisan cache: `APP_DEBUG=false`, `APP_ENV=production`, `LOG_LEVEL=warning`, Redis для cache/session/queue, OPcache, затем `php artisan optimize`, `config:cache`, `route:cache`, `view:cache`.
2. Остановить запись `Pending` cookie consent в БД: до accept/reject держать состояние только в cookie, затем запустить cleanup старых pending-строк в `cookie_consents`.
3. Добавить `vite.config.js`, выполнить production build и убрать одновременное подключение `public.scss` + `private.scss` + `app.scss` там, где страница использует только один layout.
4. Включить cache headers и gzip/brotli для `public/build`, fonts, images и Filament/vendor assets; для hashed файлов поставить `Cache-Control: public, max-age=31536000, immutable`.
5. Заменить самые явные `get()->count()` на `count()` в `HomeController::index()`/`search()` и быстрый поиск перевести с `LIKE '%...%'` на существующий FULLTEXT `items(name, synonyms)` для name/synonyms plus exact lookup по `id_1c`.

После quick wins нужно снять baseline и after-метрики: 5-10 популярных страниц каталога, главная, быстрый поиск, страница товара, генерация прайса, p95/p99 за 24 часа в APM и slow query log.

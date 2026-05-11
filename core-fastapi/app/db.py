"""Database (PostgreSQL via asyncpg) and Redis connection helpers."""

import logging

import asyncpg
import redis.asyncio as aioredis

from .config import settings

logger = logging.getLogger("core.db")

_pg_pool: asyncpg.Pool | None = None
_redis: aioredis.Redis | None = None

MIGRATIONS = [
    # 000_upgrade_integer_user_ids_to_uuid — idempotent upgrade from the legacy
    # core-rust / core-django schema where users.id was SERIAL (INTEGER).  The
    # block is a no-op when users.id is already UUID.  Must run before
    # 001_initial so that the new tables that reference users(id) as UUID can be
    # created successfully.
    #
    # FK constraints referencing users.id are discovered dynamically from
    # pg_constraint so that Django-generated constraint names like
    # supplier_votes_voter_id_2e8acc32_fk_users_id (created by tables that this
    # service does not own) are dropped along with the constraints created by
    # core-rust / core-fastapi.  After the column is recreated as UUID, the FKs
    # owned by core-fastapi are restored; FKs owned by other services (Django)
    # are left for the owning service to recreate.
    """
    DO $$
    DECLARE
        col_type TEXT;
        fk RECORD;
    BEGIN
        SELECT data_type INTO col_type
        FROM information_schema.columns
        WHERE table_name = 'users' AND column_name = 'id';

        IF col_type IS NOT NULL AND col_type <> 'uuid' THEN
            -- Truncate (with CASCADE) every table that has an FK referencing
            -- users.id.  Existing INTEGER user IDs cannot be reinterpreted as
            -- UUIDs, so child rows must be discarded.  Done BEFORE the FK
            -- constraints are dropped so TRUNCATE … CASCADE can follow them
            -- and clear every downstream table in one pass.
            FOR fk IN
                SELECT DISTINCT
                       cls.relname AS table_name,
                       nsp.nspname AS schema_name
                FROM pg_constraint  con
                JOIN pg_class       cls ON cls.oid = con.conrelid
                JOIN pg_namespace   nsp ON nsp.oid = cls.relnamespace
                JOIN pg_class       ref ON ref.oid = con.confrelid
                WHERE con.contype = 'f'
                  AND ref.relname = 'users'
            LOOP
                EXECUTE format(
                    'TRUNCATE TABLE %I.%I CASCADE',
                    fk.schema_name, fk.table_name
                );
            END LOOP;
            TRUNCATE TABLE users CASCADE;

            -- Drop every FK constraint that references users.id, regardless of
            -- which service created it.  Querying pg_constraint catches both
            -- core-rust / core-fastapi names (e.g. *_user_id_fkey) and Django's
            -- hashed names (e.g. supplier_votes_voter_id_2e8acc32_fk_users_id).
            FOR fk IN
                SELECT con.conname,
                       cls.relname AS table_name,
                       nsp.nspname AS schema_name
                FROM pg_constraint  con
                JOIN pg_class       cls ON cls.oid = con.conrelid
                JOIN pg_namespace   nsp ON nsp.oid = cls.relnamespace
                JOIN pg_class       ref ON ref.oid = con.confrelid
                WHERE con.contype = 'f'
                  AND ref.relname = 'users'
            LOOP
                EXECUTE format(
                    'ALTER TABLE %I.%I DROP CONSTRAINT %I',
                    fk.schema_name, fk.table_name, fk.conname
                );
            END LOOP;

            -- Change users.id from INTEGER to UUID.
            ALTER TABLE users DROP COLUMN id;
            ALTER TABLE users ADD COLUMN id UUID PRIMARY KEY DEFAULT gen_random_uuid();

            -- Change child FK columns owned by core-fastapi from INTEGER to UUID.
            ALTER TABLE user_sessions  ALTER COLUMN user_id      TYPE UUID USING NULL;
            ALTER TABLE procurements   ALTER COLUMN organizer_id  TYPE UUID USING NULL;
            ALTER TABLE procurements   ALTER COLUMN supplier_id   TYPE UUID USING NULL;
            ALTER TABLE participants   ALTER COLUMN user_id       TYPE UUID USING NULL;
            ALTER TABLE payments       ALTER COLUMN user_id       TYPE UUID USING NULL;
            ALTER TABLE transactions   ALTER COLUMN user_id       TYPE UUID USING NULL;
            ALTER TABLE chat_messages  ALTER COLUMN user_id       TYPE UUID USING NULL;
            ALTER TABLE message_reads  ALTER COLUMN user_id       TYPE UUID USING NULL;
            ALTER TABLE notifications  ALTER COLUMN user_id       TYPE UUID USING NULL;

            -- Restore NOT NULL constraints.
            ALTER TABLE user_sessions  ALTER COLUMN user_id      SET NOT NULL;
            ALTER TABLE procurements   ALTER COLUMN organizer_id  SET NOT NULL;
            ALTER TABLE participants   ALTER COLUMN user_id       SET NOT NULL;
            ALTER TABLE payments       ALTER COLUMN user_id       SET NOT NULL;
            ALTER TABLE transactions   ALTER COLUMN user_id       SET NOT NULL;
            ALTER TABLE message_reads  ALTER COLUMN user_id       SET NOT NULL;
            ALTER TABLE notifications  ALTER COLUMN user_id       SET NOT NULL;

            -- Restore FK constraints owned by core-fastapi.  FKs from tables
            -- owned by other services (e.g. Django tables like supplier_votes,
            -- vote_close_requests, supplier_document_jobs) are intentionally
            -- NOT restored here — their owning service's migrations will
            -- recreate them with the correct UUID type when next deployed.
            ALTER TABLE user_sessions  ADD CONSTRAINT user_sessions_user_id_fkey
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE;
            ALTER TABLE procurements   ADD CONSTRAINT procurements_organizer_id_fkey
                FOREIGN KEY (organizer_id) REFERENCES users(id) ON DELETE CASCADE;
            ALTER TABLE procurements   ADD CONSTRAINT procurements_supplier_id_fkey
                FOREIGN KEY (supplier_id) REFERENCES users(id) ON DELETE SET NULL;
            ALTER TABLE participants   ADD CONSTRAINT participants_user_id_fkey
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE;
            ALTER TABLE payments       ADD CONSTRAINT payments_user_id_fkey
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE;
            ALTER TABLE transactions   ADD CONSTRAINT transactions_user_id_fkey
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE;
            ALTER TABLE chat_messages  ADD CONSTRAINT chat_messages_user_id_fkey
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE SET NULL;
            ALTER TABLE message_reads  ADD CONSTRAINT message_reads_user_id_fkey
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE;
            ALTER TABLE notifications  ADD CONSTRAINT notifications_user_id_fkey
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE;
        END IF;
    END $$;

    -- Add is_banned column introduced in core-fastapi if the table exists but lacks it.
    DO $$
    BEGIN
        IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'users') THEN
            ALTER TABLE users ADD COLUMN IF NOT EXISTS is_banned BOOLEAN NOT NULL DEFAULT FALSE;
        END IF;
    END $$;
    """,
    # 001_initial
    """
    CREATE TABLE IF NOT EXISTS users (
        id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        platform         VARCHAR(20) NOT NULL DEFAULT 'telegram',
        platform_user_id VARCHAR(100) NOT NULL,
        username         VARCHAR(100) NOT NULL DEFAULT '',
        first_name       VARCHAR(100) NOT NULL DEFAULT '',
        last_name        VARCHAR(100) NOT NULL DEFAULT '',
        phone            VARCHAR(30) NOT NULL DEFAULT '',
        email            VARCHAR(254) NOT NULL DEFAULT '',
        role             VARCHAR(20) NOT NULL DEFAULT 'buyer',
        balance          NUMERIC(12, 2) NOT NULL DEFAULT 0,
        language_code    VARCHAR(20) NOT NULL DEFAULT 'ru',
        is_active        BOOLEAN NOT NULL DEFAULT TRUE,
        is_verified      BOOLEAN NOT NULL DEFAULT FALSE,
        is_banned        BOOLEAN NOT NULL DEFAULT FALSE,
        selfie_file_id   VARCHAR(255) NOT NULL DEFAULT '',
        created_at       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        updated_at       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        UNIQUE (platform, platform_user_id)
    );

    CREATE TABLE IF NOT EXISTS user_sessions (
        id           SERIAL PRIMARY KEY,
        user_id      UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        dialog_type  VARCHAR(50) NOT NULL DEFAULT '',
        dialog_state VARCHAR(50) NOT NULL DEFAULT '',
        dialog_data  JSONB NOT NULL DEFAULT '{}',
        expires_at   TIMESTAMPTZ,
        created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        updated_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        UNIQUE (user_id)
    );

    CREATE TABLE IF NOT EXISTS categories (
        id          SERIAL PRIMARY KEY,
        name        VARCHAR(100) NOT NULL,
        description TEXT NOT NULL DEFAULT '',
        parent_id   INTEGER REFERENCES categories(id) ON DELETE CASCADE,
        icon        VARCHAR(50) NOT NULL DEFAULT '',
        is_active   BOOLEAN NOT NULL DEFAULT TRUE,
        created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
    );

    CREATE TABLE IF NOT EXISTS procurements (
        id                 SERIAL PRIMARY KEY,
        title              VARCHAR(200) NOT NULL,
        description        TEXT NOT NULL DEFAULT '',
        category_id        INTEGER REFERENCES categories(id) ON DELETE SET NULL,
        organizer_id       UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        supplier_id        UUID REFERENCES users(id) ON DELETE SET NULL,
        city               VARCHAR(100) NOT NULL DEFAULT '',
        delivery_address   TEXT NOT NULL DEFAULT '',
        target_amount      NUMERIC(12, 2) NOT NULL DEFAULT 0,
        current_amount     NUMERIC(12, 2) NOT NULL DEFAULT 0,
        stop_at_amount     NUMERIC(12, 2),
        unit               VARCHAR(20) NOT NULL DEFAULT 'units',
        price_per_unit     NUMERIC(10, 2),
        status             VARCHAR(20) NOT NULL DEFAULT 'draft',
        commission_percent NUMERIC(5, 2) NOT NULL DEFAULT 0,
        min_quantity       NUMERIC(10, 2),
        deadline           TIMESTAMPTZ NOT NULL DEFAULT NOW() + INTERVAL '30 days',
        payment_deadline   TIMESTAMPTZ,
        image_url          VARCHAR(200) NOT NULL DEFAULT '',
        is_featured        BOOLEAN NOT NULL DEFAULT FALSE,
        created_at         TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        updated_at         TIMESTAMPTZ NOT NULL DEFAULT NOW()
    );

    CREATE TABLE IF NOT EXISTS participants (
        id               SERIAL PRIMARY KEY,
        procurement_id   INTEGER NOT NULL REFERENCES procurements(id) ON DELETE CASCADE,
        user_id          UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        quantity         NUMERIC(10, 2) NOT NULL DEFAULT 1,
        amount           NUMERIC(12, 2) NOT NULL DEFAULT 0,
        status           VARCHAR(20) NOT NULL DEFAULT 'pending',
        notes            TEXT NOT NULL DEFAULT '',
        is_active        BOOLEAN NOT NULL DEFAULT TRUE,
        created_at       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        updated_at       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        UNIQUE (procurement_id, user_id)
    );

    CREATE TABLE IF NOT EXISTS payments (
        id               SERIAL PRIMARY KEY,
        user_id          UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        payment_type     VARCHAR(30) NOT NULL,
        amount           NUMERIC(12, 2) NOT NULL,
        status           VARCHAR(30) NOT NULL DEFAULT 'pending',
        external_id      VARCHAR(100) UNIQUE,
        provider         VARCHAR(50) NOT NULL DEFAULT 'yookassa',
        confirmation_url VARCHAR(200) NOT NULL DEFAULT '',
        procurement_id   INTEGER REFERENCES procurements(id) ON DELETE SET NULL,
        description      TEXT NOT NULL DEFAULT '',
        metadata         JSONB NOT NULL DEFAULT '{}',
        paid_at          TIMESTAMPTZ,
        created_at       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        updated_at       TIMESTAMPTZ NOT NULL DEFAULT NOW()
    );

    CREATE TABLE IF NOT EXISTS transactions (
        id               SERIAL PRIMARY KEY,
        user_id          UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        transaction_type VARCHAR(30) NOT NULL,
        amount           NUMERIC(12, 2) NOT NULL,
        balance_after    NUMERIC(12, 2) NOT NULL DEFAULT 0,
        payment_id       INTEGER REFERENCES payments(id) ON DELETE SET NULL,
        procurement_id   INTEGER REFERENCES procurements(id) ON DELETE SET NULL,
        description      TEXT NOT NULL DEFAULT '',
        created_at       TIMESTAMPTZ NOT NULL DEFAULT NOW()
    );

    CREATE TABLE IF NOT EXISTS chat_messages (
        id             SERIAL PRIMARY KEY,
        procurement_id INTEGER NOT NULL REFERENCES procurements(id) ON DELETE CASCADE,
        user_id        UUID REFERENCES users(id) ON DELETE SET NULL,
        message_type   VARCHAR(20) NOT NULL DEFAULT 'text',
        text           TEXT NOT NULL DEFAULT '',
        attachment_url VARCHAR(200) NOT NULL DEFAULT '',
        is_edited      BOOLEAN NOT NULL DEFAULT FALSE,
        is_deleted     BOOLEAN NOT NULL DEFAULT FALSE,
        created_at     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        updated_at     TIMESTAMPTZ NOT NULL DEFAULT NOW()
    );

    CREATE TABLE IF NOT EXISTS message_reads (
        id                   SERIAL PRIMARY KEY,
        user_id              UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        procurement_id       INTEGER NOT NULL REFERENCES procurements(id) ON DELETE CASCADE,
        last_read_message_id INTEGER REFERENCES chat_messages(id) ON DELETE SET NULL,
        last_read_at         TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        UNIQUE (user_id, procurement_id)
    );

    CREATE TABLE IF NOT EXISTS notifications (
        id                SERIAL PRIMARY KEY,
        user_id           UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        notification_type VARCHAR(30) NOT NULL,
        title             VARCHAR(200) NOT NULL DEFAULT '',
        message           TEXT NOT NULL DEFAULT '',
        procurement_id    INTEGER REFERENCES procurements(id) ON DELETE CASCADE,
        is_read           BOOLEAN NOT NULL DEFAULT FALSE,
        created_at        TIMESTAMPTZ NOT NULL DEFAULT NOW()
    );

    CREATE INDEX IF NOT EXISTS idx_users_platform ON users(platform, platform_user_id);
    CREATE INDEX IF NOT EXISTS idx_users_role ON users(role);
    CREATE INDEX IF NOT EXISTS idx_procurements_status ON procurements(status);
    CREATE INDEX IF NOT EXISTS idx_procurements_organizer ON procurements(organizer_id);
    CREATE INDEX IF NOT EXISTS idx_chat_messages_procurement ON chat_messages(procurement_id, created_at);
    CREATE INDEX IF NOT EXISTS idx_notifications_user ON notifications(user_id, is_read);

    -- Buyer requests (issue #194: form 1.1 "Создать запрос")
    CREATE TABLE IF NOT EXISTS buyer_requests (
        id           SERIAL PRIMARY KEY,
        user_id      UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        product_name VARCHAR(200) NOT NULL,
        quantity     NUMERIC(10, 2) NOT NULL DEFAULT 1,
        unit         VARCHAR(20) NOT NULL DEFAULT 'units',
        city         VARCHAR(100) NOT NULL DEFAULT '',
        notes        TEXT NOT NULL DEFAULT '',
        is_active    BOOLEAN NOT NULL DEFAULT TRUE,
        created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        updated_at   TIMESTAMPTZ NOT NULL DEFAULT NOW()
    );
    CREATE INDEX IF NOT EXISTS idx_buyer_requests_user ON buyer_requests(user_id, is_active);
    CREATE INDEX IF NOT EXISTS idx_buyer_requests_product ON buyer_requests(LOWER(product_name));

    -- News feed (issue #194: published by organizers/suppliers)
    CREATE TABLE IF NOT EXISTS news_posts (
        id          SERIAL PRIMARY KEY,
        author_id   UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        title       VARCHAR(200) NOT NULL,
        content     TEXT NOT NULL DEFAULT '',
        is_deleted  BOOLEAN NOT NULL DEFAULT FALSE,
        created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        updated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
    );
    CREATE INDEX IF NOT EXISTS idx_news_author ON news_posts(author_id);
    CREATE INDEX IF NOT EXISTS idx_news_created_at ON news_posts(created_at DESC);

    -- Polls (issue #194: voting for supplier or arbitrary group decisions)
    CREATE TABLE IF NOT EXISTS polls (
        id              SERIAL PRIMARY KEY,
        procurement_id  INTEGER REFERENCES procurements(id) ON DELETE CASCADE,
        author_id       UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        question        VARCHAR(255) NOT NULL,
        poll_type       VARCHAR(20) NOT NULL DEFAULT 'general',
        is_closed       BOOLEAN NOT NULL DEFAULT FALSE,
        created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
    );
    CREATE TABLE IF NOT EXISTS poll_options (
        id        SERIAL PRIMARY KEY,
        poll_id   INTEGER NOT NULL REFERENCES polls(id) ON DELETE CASCADE,
        text      VARCHAR(200) NOT NULL,
        position  INTEGER NOT NULL DEFAULT 0
    );
    CREATE TABLE IF NOT EXISTS poll_votes (
        id          SERIAL PRIMARY KEY,
        poll_id     INTEGER NOT NULL REFERENCES polls(id) ON DELETE CASCADE,
        option_id   INTEGER NOT NULL REFERENCES poll_options(id) ON DELETE CASCADE,
        user_id     UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        UNIQUE (poll_id, user_id)
    );
    CREATE INDEX IF NOT EXISTS idx_polls_procurement ON polls(procurement_id);

    -- Supplier company cards (issue #194: form 3.1)
    CREATE TABLE IF NOT EXISTS supplier_companies (
        id              SERIAL PRIMARY KEY,
        user_id         UUID NOT NULL UNIQUE REFERENCES users(id) ON DELETE CASCADE,
        name            VARCHAR(255) NOT NULL,
        legal_address   TEXT NOT NULL DEFAULT '',
        postal_address  TEXT NOT NULL DEFAULT '',
        actual_address  TEXT NOT NULL DEFAULT '',
        okved           VARCHAR(50) NOT NULL DEFAULT '',
        ogrn            VARCHAR(50) NOT NULL DEFAULT '',
        inn             VARCHAR(20) NOT NULL DEFAULT '',
        contact_phone   VARCHAR(30) NOT NULL DEFAULT '',
        email           VARCHAR(254) NOT NULL DEFAULT '',
        is_published    BOOLEAN NOT NULL DEFAULT TRUE,
        created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
    );

    -- Supplier price lists (issue #194: form 3.2)
    CREATE TABLE IF NOT EXISTS supplier_price_lists (
        id              SERIAL PRIMARY KEY,
        supplier_id     UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        file_url        VARCHAR(255) NOT NULL DEFAULT '',
        popular_items   JSONB NOT NULL DEFAULT '[]',
        is_published    BOOLEAN NOT NULL DEFAULT TRUE,
        created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
    );
    CREATE INDEX IF NOT EXISTS idx_price_lists_supplier ON supplier_price_lists(supplier_id);

    -- Invitations (issue #194: organizer invites supplier or buyer)
    CREATE TABLE IF NOT EXISTS invitations (
        id              SERIAL PRIMARY KEY,
        organizer_id    UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        invitee_id      UUID REFERENCES users(id) ON DELETE SET NULL,
        invitee_email   VARCHAR(254) NOT NULL DEFAULT '',
        invitee_role    VARCHAR(20) NOT NULL DEFAULT 'supplier',
        procurement_id  INTEGER REFERENCES procurements(id) ON DELETE SET NULL,
        message         TEXT NOT NULL DEFAULT '',
        status          VARCHAR(20) NOT NULL DEFAULT 'pending',
        created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
    );
    CREATE INDEX IF NOT EXISTS idx_invitations_invitee ON invitations(invitee_id, status);
    CREATE INDEX IF NOT EXISTS idx_invitations_email ON invitations(LOWER(invitee_email), status);

    -- Closing documents (issue #194: form 3.3, supplier sends closing docs to buyers)
    CREATE TABLE IF NOT EXISTS closing_documents (
        id              SERIAL PRIMARY KEY,
        procurement_id  INTEGER NOT NULL REFERENCES procurements(id) ON DELETE CASCADE,
        supplier_id     UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        file_url        VARCHAR(255) NOT NULL DEFAULT '',
        comment         TEXT NOT NULL DEFAULT '',
        created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
    );

    -- Withdrawal requests (issue #194: form 1.4 "Вывод средств")
    CREATE TABLE IF NOT EXISTS withdrawal_requests (
        id            SERIAL PRIMARY KEY,
        user_id       UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        amount        NUMERIC(12, 2) NOT NULL,
        bank_details  TEXT NOT NULL DEFAULT '',
        status        VARCHAR(20) NOT NULL DEFAULT 'pending',
        processed_at  TIMESTAMPTZ,
        created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW()
    );
    CREATE INDEX IF NOT EXISTS idx_withdrawals_user ON withdrawal_requests(user_id, status);
    """,
    # 002_seed_categories — idempotent seed for top-level + child categories.
    # The categories table has no UNIQUE constraint on name, so we guard with
    # WHERE NOT EXISTS instead of ON CONFLICT.
    """
    INSERT INTO categories (name, description, icon, parent_id)
    SELECT v.name, v.description, v.icon, NULL
    FROM (VALUES
        ('Продукты питания',       'Еда, напитки, бакалея',                                 '🍎'),
        ('Товары для дома',        'Бытовая химия, хозяйственные товары',                   '🏠'),
        ('Одежда и обувь',         'Одежда, обувь, аксессуары',                             '👗'),
        ('Электроника',            'Гаджеты, техника, комплектующие',                       '📱'),
        ('Косметика и здоровье',   'Уходовая косметика, медикаменты, витамины',             '💄'),
        ('Детские товары',         'Игрушки, товары для новорождённых, школьные принадлежности', '🧸'),
        ('Сад и огород',           'Семена, рассада, удобрения, садовый инвентарь',         '🌱'),
        ('Строительство и ремонт', 'Стройматериалы, инструменты, отделочные материалы',     '🏗️'),
        ('Автотовары',             'Автозапчасти, масла, аксессуары',                       '🚗'),
        ('Прочее',                 'Товары, не вошедшие в другие категории',                '📦')
    ) AS v(name, description, icon)
    WHERE NOT EXISTS (
        SELECT 1 FROM categories c WHERE c.name = v.name AND c.parent_id IS NULL
    );

    INSERT INTO categories (name, description, icon, parent_id)
    SELECT v.name, v.description, v.icon, p.id
    FROM (VALUES
        ('Продукты питания',       'Мёд и пчеловодство',         'Натуральный мёд, соты, прополис',                '🍯'),
        ('Продукты питания',       'Молочная продукция',          'Молоко, сыр, масло, йогурт',                     '🥛'),
        ('Продукты питания',       'Мясо и птица',                'Говядина, свинина, курица, индейка',             '🥩'),
        ('Продукты питания',       'Рыба и морепродукты',         'Рыба, креветки, кальмары',                       '🐟'),
        ('Продукты питания',       'Овощи и фрукты',              'Свежие овощи, фрукты, зелень',                   '🥦'),
        ('Продукты питания',       'Крупы и зерновые',            'Рис, гречка, пшеница, кукуруза',                 '🌾'),
        ('Продукты питания',       'Чай и кофе',                  'Листовой чай, кофе в зёрнах',                    '☕'),
        ('Продукты питания',       'Снеки и сладости',            'Орехи, сухофрукты, конфеты',                     '🍫'),
        ('Товары для дома',        'Бытовая химия',               'Моющие средства, стиральные порошки',            '🧴'),
        ('Товары для дома',        'Текстиль',                    'Постельное бельё, полотенца, шторы',             '🛏️'),
        ('Товары для дома',        'Посуда и кухня',              'Кастрюли, сковороды, столовые приборы',          '🍳'),
        ('Товары для дома',        'Инструменты',                 'Ручной и электрический инструмент',              '🔧'),
        ('Одежда и обувь',         'Женская одежда',              'Платья, блузки, юбки, джинсы',                   '👚'),
        ('Одежда и обувь',         'Мужская одежда',              'Рубашки, брюки, куртки',                         '👔'),
        ('Одежда и обувь',         'Детская одежда',              'Одежда для детей всех возрастов',                '👶'),
        ('Одежда и обувь',         'Обувь',                       'Туфли, кроссовки, сапоги, ботинки',              '👟'),
        ('Одежда и обувь',         'Аксессуары',                  'Сумки, ремни, шарфы, перчатки',                  '👜'),
        ('Электроника',            'Смартфоны и планшеты',        'Телефоны, планшеты, аксессуары',                 '📱'),
        ('Электроника',            'Компьютеры',                  'Ноутбуки, комплектующие, периферия',             '💻'),
        ('Электроника',            'Бытовая техника',             'Холодильники, стиральные машины, пылесосы',      '📟'),
        ('Электроника',            'Освещение',                   'Лампы, светильники, LED-ленты',                  '💡'),
        ('Косметика и здоровье',   'Уход за лицом',               'Кремы, маски, сыворотки',                        '🧖'),
        ('Косметика и здоровье',   'Уход за телом',               'Лосьоны, скрабы, мыло',                          '🧴'),
        ('Косметика и здоровье',   'Витамины и добавки',          'БАДы, витаминные комплексы',                     '💊'),
        ('Косметика и здоровье',   'Спорт и фитнес',              'Спортивное питание, инвентарь',                  '🏋️'),
        ('Детские товары',         'Игрушки',                     'Развивающие игры, конструкторы, куклы',          '🎮'),
        ('Детские товары',         'Товары для новорождённых',    'Памперсы, питание, коляски',                     '🍼'),
        ('Детские товары',         'Школьные принадлежности',     'Тетради, ручки, рюкзаки',                        '📒'),
        ('Сад и огород',           'Семена и рассада',            'Овощи, цветы, ягоды',                            '🌿'),
        ('Сад и огород',           'Удобрения',                   'Минеральные и органические удобрения',           '🌱'),
        ('Сад и огород',           'Садовый инвентарь',           'Лопаты, грабли, шланги',                         '⛏️'),
        ('Строительство и ремонт', 'Стройматериалы',              'Кирпич, цемент, доска, арматура',                '🧱'),
        ('Строительство и ремонт', 'Отделочные материалы',        'Обои, плитка, ламинат, краска',                  '🎨'),
        ('Строительство и ремонт', 'Сантехника',                  'Трубы, краны, унитазы, ванны',                   '🚿'),
        ('Автотовары',             'Шины и диски',                'Летние и зимние шины, диски',                    '🔄'),
        ('Автотовары',             'Автохимия',                   'Масла, антифризы, автомойка',                    '🛢️'),
        ('Автотовары',             'Автоаксессуары',              'Коврики, чехлы, ароматизаторы',                  '🚙')
    ) AS v(parent_name, name, description, icon)
    JOIN categories p ON p.name = v.parent_name AND p.parent_id IS NULL
    WHERE NOT EXISTS (
        SELECT 1 FROM categories c WHERE c.name = v.name AND c.parent_id = p.id
    );
    """,
]


def _normalize_pg_dsn(url: str) -> str:
    if url.startswith("postgresql+asyncpg://"):
        return url.replace("postgresql+asyncpg://", "postgresql://", 1)
    return url


async def connect() -> None:
    global _pg_pool, _redis

    dsn = _normalize_pg_dsn(settings.database_url)
    _pg_pool = await asyncpg.create_pool(dsn=dsn, min_size=2, max_size=10)
    async with _pg_pool.acquire() as conn:
        await conn.execute("SELECT 1")
    logger.info("PostgreSQL connection established")

    try:
        _redis = aioredis.from_url(settings.redis_url, decode_responses=True)
        await _redis.ping()
        logger.info("Redis connection established")
    except Exception as exc:
        logger.warning("Redis unavailable: %s", exc)
        _redis = None


async def disconnect() -> None:
    global _pg_pool, _redis
    if _pg_pool is not None:
        await _pg_pool.close()
        _pg_pool = None
    if _redis is not None:
        await _redis.aclose()
        _redis = None


def get_pool() -> asyncpg.Pool:
    if _pg_pool is None:
        raise RuntimeError("PostgreSQL pool is not initialised")
    return _pg_pool


def get_redis() -> aioredis.Redis | None:
    return _redis


async def init_schema() -> None:
    pool = get_pool()
    async with pool.acquire() as conn:
        for migration in MIGRATIONS:
            await conn.execute(migration)
    logger.info("Database schema initialized")

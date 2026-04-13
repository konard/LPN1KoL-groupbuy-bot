-- Initial database schema for GroupBuy service
-- Compatible with existing Django-created tables

-- Users table
CREATE TABLE IF NOT EXISTS users (
    id SERIAL PRIMARY KEY,
    platform VARCHAR(20) NOT NULL DEFAULT 'telegram',
    platform_user_id VARCHAR(100) NOT NULL,
    username VARCHAR(100) NOT NULL DEFAULT '',
    first_name VARCHAR(100) NOT NULL,
    last_name VARCHAR(100) NOT NULL DEFAULT '',
    phone VARCHAR(30) NOT NULL DEFAULT '',
    email VARCHAR(254) NOT NULL DEFAULT '',
    role VARCHAR(20) NOT NULL DEFAULT 'buyer',
    balance DECIMAL(12, 2) NOT NULL DEFAULT 0,
    language_code VARCHAR(20) NOT NULL DEFAULT 'ru',
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    is_verified BOOLEAN NOT NULL DEFAULT FALSE,
    selfie_file_id VARCHAR(255) NOT NULL DEFAULT '',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (platform, platform_user_id)
);

CREATE INDEX IF NOT EXISTS idx_users_platform ON users(platform, platform_user_id);
CREATE INDEX IF NOT EXISTS idx_users_role ON users(role);
CREATE INDEX IF NOT EXISTS idx_users_created_at ON users(created_at);

-- User sessions table
CREATE TABLE IF NOT EXISTS user_sessions (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    dialog_type VARCHAR(50) NOT NULL DEFAULT '',
    dialog_state VARCHAR(50) NOT NULL DEFAULT '',
    dialog_data JSONB NOT NULL DEFAULT '{}',
    expires_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_user_sessions_user_dialog ON user_sessions(user_id, dialog_type);

-- Categories table
CREATE TABLE IF NOT EXISTS categories (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    parent_id INTEGER REFERENCES categories(id) ON DELETE CASCADE,
    icon VARCHAR(50) NOT NULL DEFAULT '',
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Procurements table
CREATE TABLE IF NOT EXISTS procurements (
    id SERIAL PRIMARY KEY,
    title VARCHAR(200) NOT NULL,
    description TEXT NOT NULL,
    category_id INTEGER REFERENCES categories(id) ON DELETE SET NULL,
    organizer_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    supplier_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
    city VARCHAR(100) NOT NULL,
    delivery_address TEXT NOT NULL DEFAULT '',
    target_amount DECIMAL(12, 2) NOT NULL,
    current_amount DECIMAL(12, 2) NOT NULL DEFAULT 0,
    stop_at_amount DECIMAL(12, 2),
    unit VARCHAR(20) NOT NULL DEFAULT 'units',
    price_per_unit DECIMAL(10, 2),
    status VARCHAR(20) NOT NULL DEFAULT 'draft',
    deadline TIMESTAMPTZ NOT NULL,
    payment_deadline TIMESTAMPTZ,
    image_url VARCHAR(200) NOT NULL DEFAULT '',
    is_featured BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_procurements_status ON procurements(status);
CREATE INDEX IF NOT EXISTS idx_procurements_organizer ON procurements(organizer_id);
CREATE INDEX IF NOT EXISTS idx_procurements_category ON procurements(category_id);
CREATE INDEX IF NOT EXISTS idx_procurements_city ON procurements(city);
CREATE INDEX IF NOT EXISTS idx_procurements_deadline ON procurements(deadline);
CREATE INDEX IF NOT EXISTS idx_procurements_created_at ON procurements(created_at);

-- Participants table
CREATE TABLE IF NOT EXISTS participants (
    id SERIAL PRIMARY KEY,
    procurement_id INTEGER NOT NULL REFERENCES procurements(id) ON DELETE CASCADE,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    quantity DECIMAL(10, 2) NOT NULL DEFAULT 1,
    amount DECIMAL(12, 2) NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'pending',
    notes TEXT NOT NULL DEFAULT '',
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (procurement_id, user_id)
);

CREATE INDEX IF NOT EXISTS idx_participants_procurement_status ON participants(procurement_id, status);
CREATE INDEX IF NOT EXISTS idx_participants_user ON participants(user_id);

-- Payments table
CREATE TABLE IF NOT EXISTS payments (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    payment_type VARCHAR(30) NOT NULL,
    amount DECIMAL(12, 2) NOT NULL,
    status VARCHAR(30) NOT NULL DEFAULT 'pending',
    external_id VARCHAR(100) UNIQUE,
    provider VARCHAR(50) NOT NULL DEFAULT 'yookassa',
    confirmation_url VARCHAR(200) NOT NULL DEFAULT '',
    procurement_id INTEGER REFERENCES procurements(id) ON DELETE SET NULL,
    description TEXT NOT NULL DEFAULT '',
    metadata JSONB NOT NULL DEFAULT '{}',
    paid_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_payments_user_status ON payments(user_id, status);
CREATE INDEX IF NOT EXISTS idx_payments_external_id ON payments(external_id);
CREATE INDEX IF NOT EXISTS idx_payments_created_at ON payments(created_at);

-- Transactions table
CREATE TABLE IF NOT EXISTS transactions (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    transaction_type VARCHAR(30) NOT NULL,
    amount DECIMAL(12, 2) NOT NULL,
    balance_after DECIMAL(12, 2) NOT NULL,
    payment_id INTEGER REFERENCES payments(id) ON DELETE SET NULL,
    procurement_id INTEGER REFERENCES procurements(id) ON DELETE SET NULL,
    description TEXT NOT NULL DEFAULT '',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_transactions_user_created ON transactions(user_id, created_at);
CREATE INDEX IF NOT EXISTS idx_transactions_type ON transactions(transaction_type);

-- Chat messages table
CREATE TABLE IF NOT EXISTS chat_messages (
    id SERIAL PRIMARY KEY,
    procurement_id INTEGER NOT NULL REFERENCES procurements(id) ON DELETE CASCADE,
    user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
    message_type VARCHAR(20) NOT NULL DEFAULT 'text',
    text TEXT NOT NULL,
    attachment_url VARCHAR(200) NOT NULL DEFAULT '',
    is_edited BOOLEAN NOT NULL DEFAULT FALSE,
    is_deleted BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_chat_messages_procurement_created ON chat_messages(procurement_id, created_at);
CREATE INDEX IF NOT EXISTS idx_chat_messages_user ON chat_messages(user_id);

-- Message reads table
CREATE TABLE IF NOT EXISTS message_reads (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    procurement_id INTEGER NOT NULL REFERENCES procurements(id) ON DELETE CASCADE,
    last_read_message_id INTEGER REFERENCES chat_messages(id) ON DELETE SET NULL,
    last_read_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (user_id, procurement_id)
);

-- Notifications table
CREATE TABLE IF NOT EXISTS notifications (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    notification_type VARCHAR(30) NOT NULL,
    title VARCHAR(200) NOT NULL,
    message TEXT NOT NULL,
    procurement_id INTEGER REFERENCES procurements(id) ON DELETE CASCADE,
    is_read BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_notifications_user_read ON notifications(user_id, is_read);
CREATE INDEX IF NOT EXISTS idx_notifications_created_at ON notifications(created_at);

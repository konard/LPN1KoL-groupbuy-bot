-- Migration: 005_financial_precision
-- Upgrades all monetary columns from DECIMAL(12,2) to DECIMAL(19,4).
-- DECIMAL(19,4) is the financial industry standard that prevents floating-point
-- rounding errors on amounts up to 999,999,999,999,999.9999.
-- Using float/double for currency is a data-integrity crime.

-- users.balance
ALTER TABLE users ALTER COLUMN balance TYPE DECIMAL(19, 4);

-- procurements: all monetary amounts
ALTER TABLE procurements ALTER COLUMN target_amount TYPE DECIMAL(19, 4);
ALTER TABLE procurements ALTER COLUMN current_amount TYPE DECIMAL(19, 4);
ALTER TABLE procurements ALTER COLUMN stop_at_amount TYPE DECIMAL(19, 4);
ALTER TABLE procurements ALTER COLUMN price_per_unit TYPE DECIMAL(19, 4);

-- participants.amount
ALTER TABLE participants ALTER COLUMN quantity TYPE DECIMAL(19, 4);
ALTER TABLE participants ALTER COLUMN amount TYPE DECIMAL(19, 4);

-- payments.amount
ALTER TABLE payments ALTER COLUMN amount TYPE DECIMAL(19, 4);

-- transactions: amount and running balance
ALTER TABLE transactions ALTER COLUMN amount TYPE DECIMAL(19, 4);
ALTER TABLE transactions ALTER COLUMN balance_after TYPE DECIMAL(19, 4);

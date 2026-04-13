-- Widen phone and language_code columns to avoid "value too long" errors.
--
-- phone:          VARCHAR(20) → VARCHAR(30)  (international numbers with formatting)
-- language_code:  VARCHAR(10) → VARCHAR(20)  (e.g. zh-hans-cn and similar BCP-47 tags)
--
-- Both ALTER COLUMNs are safe to run on an already-widened column, so this
-- migration is idempotent.
DO $$
BEGIN
    -- Widen phone if it is still the narrow VARCHAR(20)
    IF EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'users'
          AND column_name = 'phone'
          AND character_maximum_length <= 20
    ) THEN
        ALTER TABLE users ALTER COLUMN phone TYPE VARCHAR(30);
    END IF;

    -- Widen language_code if it is still the narrow VARCHAR(10)
    IF EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'users'
          AND column_name = 'language_code'
          AND character_maximum_length <= 10
    ) THEN
        ALTER TABLE users ALTER COLUMN language_code TYPE VARCHAR(20);
    END IF;
END
$$;

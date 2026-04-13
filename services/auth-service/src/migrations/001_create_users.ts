import { MigrationInterface, QueryRunner } from 'typeorm';

export class CreateUsers1000000000001 implements MigrationInterface {
  name = 'CreateUsers1000000000001';

  async up(queryRunner: QueryRunner): Promise<void> {
    await queryRunner.query(`CREATE EXTENSION IF NOT EXISTS "uuid-ossp"`);

    await queryRunner.query(`
      DO $$ BEGIN
        CREATE TYPE user_role AS ENUM ('user', 'admin', 'moderator', 'organizer', 'supplier', 'buyer');
      EXCEPTION
        WHEN duplicate_object THEN NULL;
      END $$
    `);

    await queryRunner.query(`
      CREATE TABLE IF NOT EXISTS users (
        id                  UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
        email               VARCHAR(255) NOT NULL,
        password_hash       VARCHAR(255) NOT NULL,
        first_name          VARCHAR(100),
        last_name           VARCHAR(100),
        role                user_role NOT NULL DEFAULT 'user',
        is_active           BOOLEAN NOT NULL DEFAULT TRUE,
        is_email_verified   BOOLEAN NOT NULL DEFAULT FALSE,
        refresh_token_hash  VARCHAR(255),
        two_factor_secret   VARCHAR(255),
        two_factor_enabled  BOOLEAN NOT NULL DEFAULT FALSE,
        backup_codes        TEXT,
        two_factor_required BOOLEAN NOT NULL DEFAULT FALSE,
        last_login_at       TIMESTAMPTZ,
        created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        CONSTRAINT users_email_unique UNIQUE (email)
      )
    `);

    await queryRunner.query(`CREATE INDEX IF NOT EXISTS idx_users_email ON users (email)`);
    await queryRunner.query(`CREATE INDEX IF NOT EXISTS idx_users_role ON users (role)`);
    await queryRunner.query(`CREATE INDEX IF NOT EXISTS idx_users_is_active ON users (is_active)`);

    await queryRunner.query(`
      CREATE OR REPLACE FUNCTION update_updated_at_column()
      RETURNS TRIGGER AS $$
      BEGIN
          NEW.updated_at = NOW();
          RETURN NEW;
      END;
      $$ LANGUAGE plpgsql
    `);

    await queryRunner.query(`
      DO $$ BEGIN
        CREATE TRIGGER users_updated_at
          BEFORE UPDATE ON users
          FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
      EXCEPTION
        WHEN duplicate_object THEN NULL;
      END $$
    `);
  }

  async down(queryRunner: QueryRunner): Promise<void> {
    await queryRunner.query(`DROP TRIGGER IF EXISTS users_updated_at ON users`);
    await queryRunner.query(`DROP FUNCTION IF EXISTS update_updated_at_column`);
    await queryRunner.query(`DROP TABLE IF EXISTS users`);
    await queryRunner.query(`DROP TYPE IF EXISTS user_role`);
  }
}

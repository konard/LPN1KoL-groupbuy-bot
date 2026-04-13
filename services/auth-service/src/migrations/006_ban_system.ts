import { MigrationInterface, QueryRunner } from 'typeorm';

/**
 * Adds ban-related columns to the users table and creates the audit_bans table.
 * Fixes: column User.is_banned does not exist (QueryFailedError on /register and /login).
 */
export class BanSystem1000000000006 implements MigrationInterface {
  name = 'BanSystem1000000000006';

  async up(queryRunner: QueryRunner): Promise<void> {
    // Add ban-related columns to users
    await queryRunner.query(`
      ALTER TABLE users
        ADD COLUMN IF NOT EXISTS is_banned BOOLEAN NOT NULL DEFAULT FALSE
    `);

    await queryRunner.query(`
      ALTER TABLE users
        ADD COLUMN IF NOT EXISTS banned_at TIMESTAMPTZ
    `);

    await queryRunner.query(`
      ALTER TABLE users
        ADD COLUMN IF NOT EXISTS ban_reason TEXT
    `);

    // Audit table for ban history (append-only log)
    await queryRunner.query(`
      CREATE TABLE IF NOT EXISTS audit_bans (
        id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
        target_user_id  UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        admin_id        UUID NOT NULL,
        action          VARCHAR(20) NOT NULL CHECK (action IN ('ban', 'unban')),
        reason          TEXT NOT NULL DEFAULT '',
        metadata        JSONB NOT NULL DEFAULT '{}',
        created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
      )
    `);

    await queryRunner.query(`
      CREATE INDEX IF NOT EXISTS idx_audit_bans_target ON audit_bans (target_user_id)
    `);

    await queryRunner.query(`
      CREATE INDEX IF NOT EXISTS idx_audit_bans_admin ON audit_bans (admin_id)
    `);

    await queryRunner.query(`
      CREATE INDEX IF NOT EXISTS idx_audit_bans_created ON audit_bans (created_at DESC)
    `);

    // Partial index for fast is_banned lookups (most users are NOT banned)
    await queryRunner.query(`
      CREATE INDEX IF NOT EXISTS idx_users_is_banned ON users (is_banned) WHERE is_banned = TRUE
    `);
  }

  async down(queryRunner: QueryRunner): Promise<void> {
    await queryRunner.query(`DROP INDEX IF EXISTS idx_users_is_banned`);
    await queryRunner.query(`DROP INDEX IF EXISTS idx_audit_bans_created`);
    await queryRunner.query(`DROP INDEX IF EXISTS idx_audit_bans_admin`);
    await queryRunner.query(`DROP INDEX IF EXISTS idx_audit_bans_target`);
    await queryRunner.query(`DROP TABLE IF EXISTS audit_bans`);
    await queryRunner.query(`ALTER TABLE users DROP COLUMN IF EXISTS ban_reason`);
    await queryRunner.query(`ALTER TABLE users DROP COLUMN IF EXISTS banned_at`);
    await queryRunner.query(`ALTER TABLE users DROP COLUMN IF EXISTS is_banned`);
  }
}

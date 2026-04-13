import { MigrationInterface, QueryRunner } from 'typeorm';

export class AddPhoneColumn1000000000004 implements MigrationInterface {
  name = 'AddPhoneColumn1000000000004';

  async up(queryRunner: QueryRunner): Promise<void> {
    // Add phone column as nullable first so existing rows don't violate NOT NULL
    await queryRunner.query(`
      ALTER TABLE users
        ADD COLUMN IF NOT EXISTS phone VARCHAR(20)
    `);

    // Backfill existing rows with a temporary unique placeholder
    await queryRunner.query(`
      UPDATE users
      SET phone = CONCAT('+00', SUBSTRING(REPLACE(id::text, '-', ''), 1, 18))
      WHERE phone IS NULL
    `);

    // Now enforce NOT NULL
    await queryRunner.query(`
      ALTER TABLE users ALTER COLUMN phone SET NOT NULL
    `);

    // Add unique constraint and index
    await queryRunner.query(`
      DO $$ BEGIN
        ALTER TABLE users ADD CONSTRAINT users_phone_unique UNIQUE (phone);
      EXCEPTION
        WHEN duplicate_object THEN NULL;
      END $$
    `);

    await queryRunner.query(`
      CREATE UNIQUE INDEX IF NOT EXISTS idx_users_phone ON users (phone)
    `);

    // password_hash is no longer required: login is OTP-based via email code
    await queryRunner.query(`
      ALTER TABLE users ALTER COLUMN password_hash DROP NOT NULL
    `);
  }

  async down(queryRunner: QueryRunner): Promise<void> {
    await queryRunner.query(`DROP INDEX IF EXISTS idx_users_phone`);
    await queryRunner.query(`ALTER TABLE users DROP CONSTRAINT IF EXISTS users_phone_unique`);
    await queryRunner.query(`ALTER TABLE users DROP COLUMN IF EXISTS phone`);
    await queryRunner.query(`ALTER TABLE users ALTER COLUMN password_hash SET NOT NULL`);
  }
}

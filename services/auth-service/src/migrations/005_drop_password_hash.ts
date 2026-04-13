import { MigrationInterface, QueryRunner } from 'typeorm';

/**
 * Authentication is now OTP-based (phone + email verification code).
 * The password_hash column is no longer used and is safe to drop.
 */
export class DropPasswordHash1000000000005 implements MigrationInterface {
  name = 'DropPasswordHash1000000000005';

  async up(queryRunner: QueryRunner): Promise<void> {
    await queryRunner.query(`
      ALTER TABLE users DROP COLUMN IF EXISTS password_hash
    `);
  }

  async down(queryRunner: QueryRunner): Promise<void> {
    await queryRunner.query(`
      ALTER TABLE users ADD COLUMN IF NOT EXISTS password_hash VARCHAR(255)
    `);
  }
}

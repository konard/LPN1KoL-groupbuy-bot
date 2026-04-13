import {
  Entity,
  Column,
  PrimaryGeneratedColumn,
  CreateDateColumn,
  UpdateDateColumn,
  Index,
} from 'typeorm';

export enum UserRole {
  USER = 'user',
  ADMIN = 'admin',
  MODERATOR = 'moderator',
  ORGANIZER = 'organizer',
  SUPPLIER = 'supplier',
  BUYER = 'buyer',
}

@Entity('users')
export class User {
  @PrimaryGeneratedColumn('uuid')
  id: string;

  @Index({ unique: true })
  @Column({ unique: true, length: 20 })
  phone: string;

  @Index({ unique: true })
  @Column({ unique: true, length: 255 })
  email: string;

  @Column({ name: 'first_name', type: 'varchar', length: 100, nullable: true })
  firstName: string | null;

  @Column({ name: 'last_name', type: 'varchar', length: 100, nullable: true })
  lastName: string | null;

  @Column({
    type: 'enum',
    enum: UserRole,
    default: UserRole.USER,
  })
  role: UserRole;

  @Column({ name: 'is_active', default: true })
  isActive: boolean;

  @Column({ name: 'is_email_verified', default: false })
  isEmailVerified: boolean;

  @Column({ name: 'refresh_token_hash', type: 'varchar', nullable: true })
  refreshTokenHash: string | null;

  @Column({ name: 'two_factor_secret', type: 'varchar', length: 255, nullable: true })
  twoFactorSecret: string | null;

  @Column({ name: 'two_factor_enabled', default: false })
  twoFactorEnabled: boolean;

  @Column({ name: 'backup_codes', type: 'simple-array', nullable: true })
  backupCodes: string[] | null;

  @Column({ name: 'two_factor_required', default: false })
  twoFactorRequired: boolean;

  @Column({ name: 'last_login_at', type: 'timestamp with time zone', nullable: true })
  lastLoginAt: Date | null;

  @Column({ name: 'is_banned', default: false })
  isBanned: boolean;

  @Column({ name: 'banned_at', type: 'timestamp with time zone', nullable: true })
  bannedAt: Date | null;

  @Column({ name: 'ban_reason', type: 'text', nullable: true })
  banReason: string | null;

  @CreateDateColumn({ name: 'created_at', type: 'timestamp with time zone' })
  createdAt: Date;

  @UpdateDateColumn({ name: 'updated_at', type: 'timestamp with time zone' })
  updatedAt: Date;
}

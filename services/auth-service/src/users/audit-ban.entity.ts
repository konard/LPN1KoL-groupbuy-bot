import {
  Entity,
  Column,
  PrimaryGeneratedColumn,
  CreateDateColumn,
  Index,
} from 'typeorm';

export type BanAction = 'ban' | 'unban';

@Entity('audit_bans')
@Index(['targetUserId'])
@Index(['adminId'])
export class AuditBan {
  @PrimaryGeneratedColumn('uuid')
  id: string;

  @Column({ name: 'target_user_id', type: 'uuid' })
  targetUserId: string;

  @Column({ name: 'admin_id', type: 'uuid' })
  adminId: string;

  @Column({ type: 'varchar', length: 20 })
  action: BanAction;

  @Column({ type: 'text', default: '' })
  reason: string;

  @Column({ type: 'jsonb', default: {} })
  metadata: Record<string, any>;

  @CreateDateColumn({ name: 'created_at', type: 'timestamp with time zone' })
  createdAt: Date;
}

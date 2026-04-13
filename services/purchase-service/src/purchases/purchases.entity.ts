import {
  Entity,
  Column,
  PrimaryGeneratedColumn,
  CreateDateColumn,
  UpdateDateColumn,
  OneToOne,
} from 'typeorm';
import { VotingSession } from '../voting/voting.entity';

export enum PurchaseStatus {
  DRAFT = 'draft',
  ACTIVE = 'active',
  VOTING = 'voting',
  APPROVED = 'approved',
  PAYMENT_PENDING = 'payment_pending',
  PAYMENT_COMPLETE = 'payment_complete',
  CANCELLED = 'cancelled',
  COMPLETED = 'completed',
}

@Entity('purchases')
export class Purchase {
  @PrimaryGeneratedColumn('uuid')
  id: string;

  @Column({ length: 500 })
  title: string;

  @Column({ type: 'text', nullable: true })
  description: string | null;

  @Column({ name: 'organizer_id', type: 'uuid' })
  organizerId: string;

  @Column({
    type: 'enum',
    enum: PurchaseStatus,
    default: PurchaseStatus.ACTIVE,
  })
  status: PurchaseStatus;

  @Column({ name: 'min_participants', type: 'int', default: 2 })
  minParticipants: number;

  @Column({ name: 'max_participants', type: 'int', nullable: true })
  maxParticipants: number | null;

  @Column({ name: 'target_amount', type: 'numeric', precision: 18, scale: 2, nullable: true })
  targetAmount: number | null;

  @Column({ name: 'currency', length: 3, default: 'RUB' })
  currency: string;

  @Column({ name: 'category', type: 'varchar', length: 100, nullable: true })
  category: string | null;

  @Column({ name: 'commission_percent', type: 'numeric', precision: 4, scale: 1, default: 0 })
  commissionPercent: number;

  @Column({ name: 'escrow_required', default: false })
  escrowRequired: boolean;

  @Column({ name: 'escrow_threshold', type: 'bigint', default: 1000000 })
  escrowThreshold: number;

  @Column({ name: 'deadline_at', type: 'timestamptz', nullable: true })
  deadlineAt: Date | null;

  @Column({ name: 'closed_at', type: 'timestamptz', nullable: true })
  closedAt: Date | null;

  @Column({ type: 'jsonb', default: {} })
  metadata: Record<string, any>;

  @OneToOne(() => VotingSession, (vs) => vs.purchase, { nullable: true })
  votingSession: VotingSession | null;

  @CreateDateColumn({ name: 'created_at', type: 'timestamptz' })
  createdAt: Date;

  @UpdateDateColumn({ name: 'updated_at', type: 'timestamptz' })
  updatedAt: Date;
}

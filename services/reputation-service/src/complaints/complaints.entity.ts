import {
  Entity,
  Column,
  PrimaryGeneratedColumn,
  CreateDateColumn,
  Index,
} from 'typeorm';

export enum ComplaintType {
  FRAUD = 'fraud',
  POOR_QUALITY = 'poor_quality',
  OFFENSIVE = 'offensive',
  OTHER = 'other',
}

export enum ComplaintStatus {
  PENDING = 'pending',
  INVESTIGATING = 'investigating',
  RESOLVED = 'resolved',
  REJECTED = 'rejected',
}

@Entity('complaints')
@Index(['targetId'])
@Index(['status'])
export class Complaint {
  @PrimaryGeneratedColumn('uuid')
  id: string;

  @Column({ name: 'reporter_id', type: 'uuid' })
  reporterId: string;

  @Column({ name: 'target_id', type: 'uuid' })
  targetId: string;

  @Column({ name: 'purchase_id', type: 'uuid', nullable: true })
  purchaseId: string | null;

  @Column({
    type: 'enum',
    enum: ComplaintType,
  })
  type: ComplaintType;

  @Column({ type: 'text' })
  description: string;

  @Column({ name: 'evidence_urls', type: 'jsonb', nullable: true })
  evidenceUrls: string[] | null;

  @Column({
    type: 'enum',
    enum: ComplaintStatus,
    default: ComplaintStatus.PENDING,
  })
  status: ComplaintStatus;

  @Column({ type: 'text', nullable: true })
  resolution: string | null;

  @Column({ name: 'admin_id', type: 'uuid', nullable: true })
  adminId: string | null;

  @CreateDateColumn({ name: 'created_at', type: 'timestamp with time zone' })
  createdAt: Date;

  @Column({ name: 'resolved_at', type: 'timestamp with time zone', nullable: true })
  resolvedAt: Date | null;
}

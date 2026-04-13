import {
  Entity,
  Column,
  PrimaryGeneratedColumn,
  CreateDateColumn,
  UpdateDateColumn,
  Index,
} from 'typeorm';

export enum ReviewRole {
  ORGANIZER = 'organizer',
  SUPPLIER = 'supplier',
  BUYER = 'buyer',
}

export interface ReviewCategories {
  reliability?: number;
  speed?: number;
  quality?: number;
  timeliness?: number;
}

@Entity('reviews')
@Index(['targetId'])
@Index(['reviewerId', 'purchaseId'], { unique: true })
export class Review {
  @PrimaryGeneratedColumn('uuid')
  id: string;

  @Column({ name: 'reviewer_id', type: 'uuid' })
  reviewerId: string;

  @Column({ name: 'target_id', type: 'uuid' })
  targetId: string;

  @Column({ name: 'purchase_id', type: 'uuid' })
  purchaseId: string;

  @Column({
    type: 'enum',
    enum: ReviewRole,
  })
  role: ReviewRole;

  @Column({ type: 'smallint' })
  rating: number;

  @Column({ type: 'jsonb', nullable: true })
  categories: ReviewCategories | null;

  @Column({ type: 'text', nullable: true })
  comment: string | null;

  @Column({ name: 'expires_at', type: 'timestamp with time zone' })
  expiresAt: Date;

  @CreateDateColumn({ name: 'created_at', type: 'timestamp with time zone' })
  createdAt: Date;

  @UpdateDateColumn({ name: 'updated_at', type: 'timestamp with time zone' })
  updatedAt: Date;
}

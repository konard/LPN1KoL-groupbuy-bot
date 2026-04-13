import {
  Entity,
  Column,
  PrimaryGeneratedColumn,
  CreateDateColumn,
  ManyToOne,
  JoinColumn,
  Unique,
} from 'typeorm';
import { Purchase } from './purchases.entity';

export enum PurchaseUserRole {
  OWNER = 'owner',
  EDITOR = 'editor',
  /** A regular user invited by a participant or organizer to join the purchase. */
  PARTICIPANT = 'participant',
}

@Entity('purchase_users')
@Unique(['purchaseId', 'userId'])
export class PurchaseUser {
  @PrimaryGeneratedColumn('uuid')
  id: string;

  @Column({ name: 'purchase_id', type: 'uuid' })
  purchaseId: string;

  @ManyToOne(() => Purchase, { onDelete: 'CASCADE' })
  @JoinColumn({ name: 'purchase_id' })
  purchase: Purchase;

  @Column({ name: 'user_id', type: 'uuid' })
  userId: string;

  @Column({
    type: 'enum',
    enum: PurchaseUserRole,
    default: PurchaseUserRole.EDITOR,
  })
  role: PurchaseUserRole;

  @Column({ name: 'invited_by', type: 'uuid', nullable: true })
  invitedBy: string | null;

  @CreateDateColumn({ name: 'created_at', type: 'timestamptz' })
  createdAt: Date;
}

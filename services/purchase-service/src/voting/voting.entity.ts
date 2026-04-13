import {
  Entity,
  Column,
  PrimaryGeneratedColumn,
  CreateDateColumn,
  UpdateDateColumn,
  ManyToOne,
  OneToMany,
  JoinColumn,
  OneToOne,
  Unique,
} from 'typeorm';
import { Purchase } from '../purchases/purchases.entity';

export enum VotingStatus {
  OPEN = 'open',
  CLOSED = 'closed',
  CANCELLED = 'cancelled',
}

@Entity('voting_sessions')
export class VotingSession {
  @PrimaryGeneratedColumn('uuid')
  id: string;

  @Column({ name: 'purchase_id', type: 'uuid' })
  purchaseId: string;

  @OneToOne(() => Purchase, (p) => p.votingSession)
  @JoinColumn({ name: 'purchase_id' })
  purchase: Purchase;

  @Column({
    type: 'enum',
    enum: VotingStatus,
    default: VotingStatus.OPEN,
  })
  status: VotingStatus;

  @Column({ name: 'closes_at', type: 'timestamptz' })
  closesAt: Date;

  @Column({ name: 'allow_add_candidates', default: true })
  allowAddCandidates: boolean;

  @Column({ name: 'allow_change_vote', default: true })
  allowChangeVote: boolean;

  @Column({ name: 'min_votes_to_close', type: 'int', default: 1 })
  minVotesToClose: number;

  @Column({ name: 'voting_duration', type: 'int', default: 24 })
  votingDuration: number;

  @Column({ name: 'voting_ends_at', type: 'timestamptz', nullable: true })
  votingEndsAt: Date | null;

  @Column({ name: 'tie_breaker', type: 'uuid', nullable: true })
  tieBreaker: string | null;

  @Column({ name: 'candidate_deadline', type: 'timestamptz', nullable: true })
  candidateDeadline: Date | null;

  @Column({ name: 'winner_candidate_id', type: 'uuid', nullable: true })
  winnerCandidateId: string | null;

  @OneToMany(() => Candidate, (c) => c.votingSession, { cascade: true })
  candidates: Candidate[];

  @OneToMany(() => Vote, (v) => v.votingSession, { cascade: true })
  votes: Vote[];

  @CreateDateColumn({ name: 'created_at', type: 'timestamptz' })
  createdAt: Date;

  @UpdateDateColumn({ name: 'updated_at', type: 'timestamptz' })
  updatedAt: Date;
}

@Entity('candidates')
export class Candidate {
  @PrimaryGeneratedColumn('uuid')
  id: string;

  @Column({ name: 'voting_session_id', type: 'uuid' })
  votingSessionId: string;

  @ManyToOne(() => VotingSession, (vs) => vs.candidates)
  @JoinColumn({ name: 'voting_session_id' })
  votingSession: VotingSession;

  @Column({ name: 'supplier_name', length: 500 })
  supplierName: string;

  @Column({ type: 'varchar', length: 1000, nullable: true })
  description: string | null;

  @Column({ name: 'price_per_unit', type: 'numeric', precision: 18, scale: 2, nullable: true })
  pricePerUnit: number | null;

  @Column({ name: 'unit', type: 'varchar', length: 50, nullable: true })
  unit: string | null;

  @Column({ name: 'supplier_url', type: 'varchar', length: 2048, nullable: true })
  supplierUrl: string | null;

  @Column({ name: 'proposed_by', type: 'uuid' })
  proposedBy: string;

  @Column({ type: 'jsonb', default: {} })
  metadata: Record<string, any>;

  @OneToMany(() => Vote, (v) => v.candidate)
  votes: Vote[];

  @CreateDateColumn({ name: 'created_at', type: 'timestamptz' })
  createdAt: Date;
}

@Entity('votes')
@Unique(['votingSessionId', 'userId'])
export class Vote {
  @PrimaryGeneratedColumn('uuid')
  id: string;

  @Column({ name: 'voting_session_id', type: 'uuid' })
  votingSessionId: string;

  @ManyToOne(() => VotingSession, (vs) => vs.votes)
  @JoinColumn({ name: 'voting_session_id' })
  votingSession: VotingSession;

  @Column({ name: 'candidate_id', type: 'uuid' })
  candidateId: string;

  @ManyToOne(() => Candidate, (c) => c.votes)
  @JoinColumn({ name: 'candidate_id' })
  candidate: Candidate;

  @Column({ name: 'user_id', type: 'uuid' })
  userId: string;

  @Column({ type: 'text', nullable: true })
  comment: string | null;

  @Column({ name: 'changed_count', type: 'int', default: 0 })
  changedCount: number;

  @CreateDateColumn({ name: 'created_at', type: 'timestamptz' })
  createdAt: Date;

  @UpdateDateColumn({ name: 'updated_at', type: 'timestamptz' })
  updatedAt: Date;
}

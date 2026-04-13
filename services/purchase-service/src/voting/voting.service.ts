import {
  Injectable,
  NotFoundException,
  BadRequestException,
  ForbiddenException,
  Logger,
} from '@nestjs/common';
import { InjectRepository } from '@nestjs/typeorm';
import { Repository, DataSource } from 'typeorm';
import { Cron, CronExpression } from '@nestjs/schedule';
import { VotingSession, VotingStatus, Candidate, Vote } from './voting.entity';
import { Purchase, PurchaseStatus } from '../purchases/purchases.entity';
import { KafkaProducer } from '../kafka/kafka.producer';

export interface CreateVotingSessionDto {
  purchaseId: string;
  closesAt: Date;
  allowAddCandidates?: boolean;
  allowChangeVote?: boolean;
  minVotesToClose?: number;
  votingDuration?: number;
}

export interface AddCandidateDto {
  supplierName: string;
  description?: string;
  pricePerUnit?: number;
  unit?: string;
  supplierUrl?: string;
  metadata?: Record<string, any>;
}

export interface CastVoteDto {
  candidateId: string;
  comment?: string;
}

@Injectable()
export class VotingService {
  private readonly logger = new Logger(VotingService.name);

  constructor(
    @InjectRepository(VotingSession)
    private readonly sessionRepo: Repository<VotingSession>,
    @InjectRepository(Candidate)
    private readonly candidateRepo: Repository<Candidate>,
    @InjectRepository(Vote)
    private readonly voteRepo: Repository<Vote>,
    @InjectRepository(Purchase)
    private readonly purchaseRepo: Repository<Purchase>,
    private readonly dataSource: DataSource,
    private readonly kafkaProducer: KafkaProducer,
  ) {}

  // ─── Create Voting Session ─────────────────────────────────────────────────

  async createSession(dto: CreateVotingSessionDto): Promise<VotingSession> {
    const purchase = await this.purchaseRepo.findOne({
      where: { id: dto.purchaseId },
    });
    if (!purchase) throw new NotFoundException('Purchase not found');
    if (purchase.status !== PurchaseStatus.DRAFT && purchase.status !== PurchaseStatus.ACTIVE) {
      throw new BadRequestException('Voting can only be started for draft or active purchases');
    }

    if (dto.closesAt <= new Date()) {
      throw new BadRequestException('closesAt must be in the future');
    }

    const votingDuration = dto.votingDuration ?? 24;
    if (votingDuration < 1 || votingDuration > 168) {
      throw new BadRequestException('votingDuration must be between 1 and 168 hours');
    }

    const now = new Date();
    const votingEndsAt = new Date(now.getTime() + votingDuration * 60 * 60 * 1000);
    const candidateDeadline = new Date(votingEndsAt.getTime() - 1 * 60 * 60 * 1000);

    return this.dataSource.transaction(async (manager) => {
      const session = manager.create(VotingSession, {
        purchaseId: dto.purchaseId,
        closesAt: dto.closesAt,
        allowAddCandidates: dto.allowAddCandidates ?? true,
        allowChangeVote: dto.allowChangeVote ?? true,
        minVotesToClose: dto.minVotesToClose ?? 1,
        votingDuration,
        votingEndsAt,
        candidateDeadline,
        tieBreaker: null,
        status: VotingStatus.OPEN,
      });
      const saved = await manager.save(VotingSession, session);

      await manager.update(Purchase, dto.purchaseId, {
        status: PurchaseStatus.VOTING,
      });

      await this.kafkaProducer.send('purchase.voting.started', {
        purchaseId: dto.purchaseId,
        sessionId: saved.id,
        closesAt: dto.closesAt,
        votingEndsAt: votingEndsAt.toISOString(),
        candidateDeadline: candidateDeadline.toISOString(),
      });

      return saved;
    });
  }

  // ─── Add Candidate ─────────────────────────────────────────────────────────

  async addCandidate(
    sessionId: string,
    userId: string,
    dto: AddCandidateDto,
  ): Promise<Candidate> {
    const session = await this.getOpenSession(sessionId);

    if (!session.allowAddCandidates) {
      throw new ForbiddenException('Adding candidates is not allowed in this session');
    }

    // Block new candidates after candidateDeadline (1 hour before votingEndsAt)
    if (session.candidateDeadline && new Date() >= session.candidateDeadline) {
      throw new BadRequestException(
        'Candidate submission deadline has passed (1 hour before voting ends)',
      );
    }

    // Enforce rate limit: max 1 candidate per hour per user
    const oneHourAgo = new Date(Date.now() - 60 * 60 * 1000);
    const recentCandidate = await this.candidateRepo
      .createQueryBuilder('c')
      .where('c.voting_session_id = :sessionId', { sessionId })
      .andWhere('c.proposed_by = :userId', { userId })
      .andWhere('c.created_at > :oneHourAgo', { oneHourAgo })
      .getCount();

    if (recentCandidate > 0) {
      throw new BadRequestException('You can only add one candidate per hour');
    }

    const candidate = this.candidateRepo.create({
      votingSessionId: sessionId,
      supplierName: dto.supplierName,
      description: dto.description ?? null,
      pricePerUnit: dto.pricePerUnit ?? null,
      unit: dto.unit ?? null,
      supplierUrl: dto.supplierUrl ?? null,
      proposedBy: userId,
      metadata: dto.metadata ?? {},
    });
    const saved = await this.candidateRepo.save(candidate);

    await this.kafkaProducer.send('purchase.candidate.added', {
      sessionId,
      candidateId: saved.id,
      proposedBy: userId,
      supplierName: dto.supplierName,
    });

    return saved;
  }

  // ─── Cast / Change Vote ────────────────────────────────────────────────────

  async castVote(
    sessionId: string,
    userId: string,
    dto: CastVoteDto,
  ): Promise<Vote> {
    const session = await this.getOpenSession(sessionId);

    // Verify candidate belongs to this session
    const candidate = await this.candidateRepo.findOne({
      where: { id: dto.candidateId, votingSessionId: sessionId },
    });
    if (!candidate) throw new NotFoundException('Candidate not found in this session');

    return this.dataSource.transaction(async (manager) => {
      // Use pessimistic write lock to prevent race conditions on simultaneous votes
      const existing = await manager.findOne(Vote, {
        where: { votingSessionId: sessionId, userId },
        lock: { mode: 'pessimistic_write' },
      });

      if (existing) {
        if (!session.allowChangeVote) {
          throw new ForbiddenException('Changing vote is not allowed in this session');
        }
        // Idempotent: if already voting for this candidate, return existing vote
        if (existing.candidateId === dto.candidateId) {
          return existing;
        }

        // Rate limit: max 10 changes per minute (check updatedAt)
        if (existing.changedCount > 0) {
          const oneMinuteAgo = new Date(Date.now() - 60 * 1000);
          if (existing.updatedAt > oneMinuteAgo && existing.changedCount >= 10) {
            throw new BadRequestException('Vote change rate limit exceeded (max 10 changes/min)');
          }
        }

        // Change vote
        const oldCandidateId = existing.candidateId;
        existing.candidateId = dto.candidateId;
        existing.comment = dto.comment ?? existing.comment;
        existing.changedCount += 1;
        const updated = await manager.save(Vote, existing);

        await this.kafkaProducer.send('purchase.vote.changed', {
          sessionId,
          userId,
          oldCandidateId,
          newCandidateId: dto.candidateId,
        });

        return updated;
      }

      // New vote
      const vote = manager.create(Vote, {
        votingSessionId: sessionId,
        candidateId: dto.candidateId,
        userId,
        comment: dto.comment ?? null,
        changedCount: 0,
      });
      const saved = await manager.save(Vote, vote);

      await this.kafkaProducer.send('purchase.vote.cast', {
        sessionId,
        userId,
        candidateId: dto.candidateId,
      });

      return saved;
    });
  }

  // ─── Get Session Results ───────────────────────────────────────────────────

  /**
   * Return tally with a `voted` flag per candidate for the requesting user.
   *
   * Avoids N+1: all votes are loaded once with the session, then a single
   * subquery-equivalent lookup (`userId`-filtered scan of the loaded array)
   * determines which candidate the user voted for.
   *
   * Response shape per tally entry:
   *   { candidate, voteCount, voted: boolean }
   *
   * `voted` is true only for the ONE candidate the user cast their vote for.
   */
  async getSessionResults(
    sessionId: string,
    userId: string | null = null,
  ): Promise<{
    session: VotingSession;
    tally: Array<{ candidate: Candidate; voteCount: number; voted: boolean }>;
    winner: Candidate | null;
    currentUserCandidateId: string | null;
  }> {
    const session = await this.sessionRepo.findOne({
      where: { id: sessionId },
      relations: ['candidates', 'votes'],
    });
    if (!session) throw new NotFoundException('Voting session not found');

    // All votes already loaded — find the requesting user's choice in O(n)
    const userVote = userId
      ? session.votes.find((v) => v.userId === userId) ?? null
      : null;
    const currentUserCandidateId = userVote?.candidateId ?? null;

    // Build count map from loaded votes (no extra DB query)
    const countMap = new Map<string, number>();
    for (const vote of session.votes) {
      countMap.set(vote.candidateId, (countMap.get(vote.candidateId) ?? 0) + 1);
    }

    const tally = session.candidates.map((c) => ({
      candidate: c,
      voteCount: countMap.get(c.id) ?? 0,
      // `voted` is true for the candidate the requesting user voted for
      voted: c.id === currentUserCandidateId,
    }));
    tally.sort((a, b) => b.voteCount - a.voteCount);

    const winner =
      session.status === VotingStatus.CLOSED && session.winnerCandidateId
        ? session.candidates.find((c) => c.id === session.winnerCandidateId) ?? null
        : null;

    return { session, tally, winner, currentUserCandidateId };
  }

  // ─── Manual Close ──────────────────────────────────────────────────────────

  async closeSession(sessionId: string, requesterId: string): Promise<VotingSession> {
    const session = await this.getOpenSession(sessionId);
    const purchase = await this.purchaseRepo.findOne({ where: { id: session.purchaseId } });
    if (!purchase) throw new NotFoundException('Purchase not found');

    // Only organizer can close manually
    if (purchase.organizerId !== requesterId) {
      throw new ForbiddenException('Only the organizer can close voting');
    }
    return this.doCloseSession(session);
  }

  // ─── Scheduler: Auto-close expired sessions ────────────────────────────────

  @Cron(CronExpression.EVERY_5_MINUTES)
  async autoCloseExpiredSessions(): Promise<void> {
    const expired = await this.sessionRepo.find({
      where: { status: VotingStatus.OPEN },
      relations: ['votes', 'candidates'],
    });

    const now = new Date();
    for (const session of expired) {
      const isExpiredByClosesAt = session.closesAt <= now;
      const isExpiredByVotingEndsAt = session.votingEndsAt && session.votingEndsAt <= now;

      if (isExpiredByClosesAt || isExpiredByVotingEndsAt) {
        try {
          await this.doCloseSession(session);
          this.logger.log(`Auto-closed voting session ${session.id}`);
        } catch (err) {
          this.logger.error(`Failed to auto-close session ${session.id}: ${err}`);
        }
      }
    }
  }

  // ─── Internal: Close Session ───────────────────────────────────────────────

  private async doCloseSession(session: VotingSession): Promise<VotingSession> {
    return this.dataSource.transaction(async (manager) => {
      // Lock the session row to prevent concurrent close operations
      const lockedSession = await manager.findOne(VotingSession, {
        where: { id: session.id },
        lock: { mode: 'pessimistic_write' },
      });
      if (!lockedSession || lockedSession.status !== VotingStatus.OPEN) {
        // Already closed by a concurrent request; return current state
        return lockedSession ?? session;
      }
      // Find winner by simple majority
      const votes = await manager.find(Vote, { where: { votingSessionId: session.id } });
      const countMap = new Map<string, number>();
      for (const v of votes) {
        countMap.set(v.candidateId, (countMap.get(v.candidateId) ?? 0) + 1);
      }

      let winnerId: string | null = null;
      let maxVotes = 0;
      let isTie = false;
      const tiedCandidateIds: string[] = [];

      for (const [candidateId, count] of countMap.entries()) {
        if (count > maxVotes) {
          maxVotes = count;
          winnerId = candidateId;
          isTie = false;
          tiedCandidateIds.length = 0;
          tiedCandidateIds.push(candidateId);
        } else if (count === maxVotes && maxVotes > 0) {
          isTie = true;
          tiedCandidateIds.push(candidateId);
        }
      }

      if (isTie) {
        // Tie detected: do not set a winner, emit tie event
        lockedSession.status = VotingStatus.CLOSED;
        lockedSession.winnerCandidateId = null;
        const saved = await manager.save(VotingSession, lockedSession);

        await this.kafkaProducer.send('voting.tie', {
          sessionId: lockedSession.id,
          purchaseId: lockedSession.purchaseId,
          tiedCandidateIds,
          voteCount: maxVotes,
          totalVotes: votes.length,
        });

        this.logger.warn(
          `Tie detected in session ${lockedSession.id} between candidates: ${tiedCandidateIds.join(', ')}`,
        );

        return saved;
      }

      lockedSession.status = VotingStatus.CLOSED;
      lockedSession.winnerCandidateId = winnerId;
      const saved = await manager.save(VotingSession, lockedSession);

      // Update purchase status
      await manager.update(Purchase, lockedSession.purchaseId, {
        status: winnerId ? PurchaseStatus.APPROVED : PurchaseStatus.CANCELLED,
        closedAt: new Date(),
      });

      await this.kafkaProducer.send('purchase.voting.closed', {
        sessionId: lockedSession.id,
        purchaseId: lockedSession.purchaseId,
        winnerId,
        totalVotes: votes.length,
      });

      return saved;
    });
  }

  // ─── Resolve Tie ──────────────────────────────────────────────────────────

  async resolveTie(sessionId: string, candidateId: string, requesterId: string): Promise<VotingSession> {
    const session = await this.sessionRepo.findOne({
      where: { id: sessionId },
      relations: ['candidates'],
    });
    if (!session) throw new NotFoundException('Voting session not found');
    if (session.status !== VotingStatus.CLOSED) {
      throw new BadRequestException('Session must be closed to resolve a tie');
    }
    if (session.winnerCandidateId) {
      throw new BadRequestException('Session already has a winner');
    }

    const purchase = await this.purchaseRepo.findOne({ where: { id: session.purchaseId } });
    if (!purchase) throw new NotFoundException('Purchase not found');
    if (purchase.organizerId !== requesterId) {
      throw new ForbiddenException('Only the organizer can resolve a tie');
    }

    // Verify candidate belongs to this session
    const candidate = session.candidates?.find((c) => c.id === candidateId);
    if (!candidate) {
      throw new NotFoundException('Candidate not found in this session');
    }

    return this.dataSource.transaction(async (manager) => {
      session.tieBreaker = candidateId;
      session.winnerCandidateId = candidateId;
      const saved = await manager.save(VotingSession, session);

      await manager.update(Purchase, session.purchaseId, {
        status: PurchaseStatus.APPROVED,
        closedAt: new Date(),
      });

      await this.kafkaProducer.send('voting.tie.resolved', {
        sessionId: session.id,
        purchaseId: session.purchaseId,
        winnerId: candidateId,
        resolvedBy: requesterId,
      });

      return saved;
    });
  }

  // ─── Helpers ───────────────────────────────────────────────────────────────

  private async getOpenSession(sessionId: string): Promise<VotingSession> {
    const session = await this.sessionRepo.findOne({ where: { id: sessionId } });
    if (!session) throw new NotFoundException('Voting session not found');
    if (session.status !== VotingStatus.OPEN) {
      throw new BadRequestException('Voting session is not open');
    }
    if (session.closesAt <= new Date()) {
      throw new BadRequestException('Voting session has expired');
    }
    return session;
  }
}

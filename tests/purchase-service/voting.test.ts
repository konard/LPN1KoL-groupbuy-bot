/**
 * Tests for long voting logic in purchase-service:
 * - Cast vote
 * - Change vote (changeable votes)
 * - Add candidate
 * - Auto-close with winner determination
 * - Validation guards (closed session, no double same-candidate vote, etc.)
 */

import { Test, TestingModule } from '@nestjs/testing';
import { getRepositoryToken } from '@nestjs/typeorm';
import { DataSource } from 'typeorm';
import { BadRequestException, ForbiddenException, NotFoundException } from '@nestjs/common';

import { VotingService } from '../../services/purchase-service/src/voting/voting.service';
import { VotingSession, VotingStatus, Candidate, Vote } from '../../services/purchase-service/src/voting/voting.entity';
import { Purchase, PurchaseStatus } from '../../services/purchase-service/src/purchases/purchases.entity';
import { KafkaProducer } from '../../services/purchase-service/src/kafka/kafka.producer';

// ─── Mock Helpers ──────────────────────────────────────────────────────────────

function makePurchase(overrides: Partial<Purchase> = {}): Purchase {
  return {
    id: 'purchase-1',
    title: 'Test Group Buy',
    description: null,
    organizerId: 'organizer-1',
    status: PurchaseStatus.DRAFT,
    minParticipants: 2,
    maxParticipants: null,
    targetAmount: null,
    currency: 'RUB',
    category: null,
    deadlineAt: null,
    closedAt: null,
    metadata: {},
    votingSession: null,
    commissionPercent: 0,
    createdAt: new Date(),
    updatedAt: new Date(),
    ...overrides,
  } as Purchase;
}

function makeSession(overrides: Partial<VotingSession> = {}): VotingSession {
  const future = new Date(Date.now() + 86400 * 1000 * 3); // 3 days from now
  return {
    id: 'session-1',
    purchaseId: 'purchase-1',
    purchase: makePurchase({ status: PurchaseStatus.VOTING }),
    status: VotingStatus.OPEN,
    closesAt: future,
    allowAddCandidates: true,
    allowChangeVote: true,
    minVotesToClose: 1,
    votingDuration: 24,
    votingEndsAt: null,
    tieBreaker: null,
    candidateDeadline: null,
    winnerCandidateId: null,
    candidates: [],
    votes: [],
    createdAt: new Date(),
    updatedAt: new Date(),
    ...overrides,
  } as VotingSession;
}

function makeCandidate(overrides: Partial<Candidate> = {}): Candidate {
  return {
    id: 'candidate-1',
    votingSessionId: 'session-1',
    votingSession: makeSession(),
    supplierName: 'Supplier A',
    description: 'Best price',
    pricePerUnit: 100,
    unit: 'kg',
    supplierUrl: 'https://supplier-a.example.com',
    proposedBy: 'user-1',
    metadata: {},
    votes: [],
    createdAt: new Date(),
    ...overrides,
  };
}

function makeVote(overrides: Partial<Vote> = {}): Vote {
  return {
    id: 'vote-1',
    votingSessionId: 'session-1',
    votingSession: makeSession(),
    candidateId: 'candidate-1',
    candidate: makeCandidate(),
    userId: 'user-1',
    comment: null,
    changedCount: 0,
    createdAt: new Date(),
    updatedAt: new Date(),
    ...overrides,
  };
}

// ─── Mock Repository Factory ──────────────────────────────────────────────────

function mockRepo<T>() {
  return {
    findOne: jest.fn(),
    find: jest.fn(),
    create: jest.fn((dto: any) => dto),
    save: jest.fn((entity: any) => Promise.resolve({ ...entity, id: entity.id || 'new-id' })),
    update: jest.fn().mockResolvedValue(undefined),
  };
}

// ─── Mock DataSource ──────────────────────────────────────────────────────────

function makeMockDataSource() {
  const manager = {
    findOne: jest.fn(),
    find: jest.fn(),
    create: jest.fn((EntityClass: any, dto: any) => dto),
    save: jest.fn((EntityClass: any, entity: any) =>
      Promise.resolve({ ...entity, id: entity.id || 'new-id' })
    ),
    update: jest.fn().mockResolvedValue(undefined),
  };
  return {
    transaction: jest.fn((fn: any) => fn(manager)),
    _manager: manager,
  };
}

// ─── Test Suite ───────────────────────────────────────────────────────────────

describe('VotingService', () => {
  let service: VotingService;
  let sessionRepo: ReturnType<typeof mockRepo>;
  let candidateRepo: ReturnType<typeof mockRepo>;
  let voteRepo: ReturnType<typeof mockRepo>;
  let purchaseRepo: ReturnType<typeof mockRepo>;
  let dataSource: ReturnType<typeof makeMockDataSource>;
  let kafkaProducer: jest.Mocked<KafkaProducer>;

  beforeEach(async () => {
    sessionRepo = mockRepo();
    candidateRepo = mockRepo();
    voteRepo = mockRepo();
    purchaseRepo = mockRepo();
    dataSource = makeMockDataSource();
    kafkaProducer = { send: jest.fn().mockResolvedValue(undefined) } as any;

    const module: TestingModule = await Test.createTestingModule({
      providers: [
        VotingService,
        { provide: getRepositoryToken(VotingSession), useValue: sessionRepo },
        { provide: getRepositoryToken(Candidate), useValue: candidateRepo },
        { provide: getRepositoryToken(Vote), useValue: voteRepo },
        { provide: getRepositoryToken(Purchase), useValue: purchaseRepo },
        { provide: DataSource, useValue: dataSource },
        { provide: KafkaProducer, useValue: kafkaProducer },
      ],
    }).compile();

    service = module.get<VotingService>(VotingService);
  });

  afterEach(() => {
    jest.clearAllMocks();
  });

  // ─── createSession ──────────────────────────────────────────────────────────

  describe('createSession', () => {
    it('creates a voting session for a draft purchase', async () => {
      const purchase = makePurchase();
      purchaseRepo.findOne.mockResolvedValue(purchase);
      dataSource._manager.save.mockImplementation((_: any, entity: any) =>
        Promise.resolve({ ...entity, id: 'session-new' })
      );
      dataSource._manager.update.mockResolvedValue(undefined);

      const closesAt = new Date(Date.now() + 86400000 * 5);
      const result = await service.createSession({
        purchaseId: 'purchase-1',
        closesAt,
        allowAddCandidates: true,
        allowChangeVote: true,
      });

      expect(result.id).toBe('session-new');
      expect(dataSource._manager.update).toHaveBeenCalledWith(
        Purchase,
        'purchase-1',
        expect.objectContaining({ status: PurchaseStatus.VOTING })
      );
      expect(kafkaProducer.send).toHaveBeenCalledWith(
        'purchase.voting.started',
        expect.objectContaining({ purchaseId: 'purchase-1' })
      );
    });

    it('throws NotFoundException if purchase does not exist', async () => {
      purchaseRepo.findOne.mockResolvedValue(null);
      await expect(
        service.createSession({
          purchaseId: 'nonexistent',
          closesAt: new Date(Date.now() + 86400000),
        })
      ).rejects.toThrow(NotFoundException);
    });

    it('throws BadRequestException if purchase is not in DRAFT status', async () => {
      purchaseRepo.findOne.mockResolvedValue(
        makePurchase({ status: PurchaseStatus.VOTING })
      );
      await expect(
        service.createSession({
          purchaseId: 'purchase-1',
          closesAt: new Date(Date.now() + 86400000),
        })
      ).rejects.toThrow(BadRequestException);
    });

    it('throws BadRequestException if closesAt is in the past', async () => {
      purchaseRepo.findOne.mockResolvedValue(makePurchase());
      await expect(
        service.createSession({
          purchaseId: 'purchase-1',
          closesAt: new Date(Date.now() - 1000), // past
        })
      ).rejects.toThrow(BadRequestException);
    });
  });

  // ─── addCandidate ──────────────────────────────────────────────────────────

  describe('addCandidate', () => {
    it('adds a new supplier candidate to an open session', async () => {
      const session = makeSession();
      sessionRepo.findOne.mockResolvedValue(session);
      candidateRepo.create.mockReturnValue({
        id: 'candidate-new',
        votingSessionId: 'session-1',
        supplierName: 'Supplier B',
        proposedBy: 'user-2',
      });
      candidateRepo.save.mockResolvedValue({
        id: 'candidate-new',
        votingSessionId: 'session-1',
        supplierName: 'Supplier B',
        proposedBy: 'user-2',
      });

      const result = await service.addCandidate('session-1', 'user-2', {
        supplierName: 'Supplier B',
        description: 'Second option',
        pricePerUnit: 90,
        unit: 'kg',
      });

      expect(result.id).toBe('candidate-new');
      expect(result.supplierName).toBe('Supplier B');
      expect(kafkaProducer.send).toHaveBeenCalledWith(
        'purchase.candidate.added',
        expect.objectContaining({
          sessionId: 'session-1',
          proposedBy: 'user-2',
          supplierName: 'Supplier B',
        })
      );
    });

    it('throws ForbiddenException when allowAddCandidates is false', async () => {
      sessionRepo.findOne.mockResolvedValue(
        makeSession({ allowAddCandidates: false })
      );
      await expect(
        service.addCandidate('session-1', 'user-1', { supplierName: 'X' })
      ).rejects.toThrow(ForbiddenException);
    });

    it('throws NotFoundException for non-existent session', async () => {
      sessionRepo.findOne.mockResolvedValue(null);
      await expect(
        service.addCandidate('nonexistent', 'user-1', { supplierName: 'X' })
      ).rejects.toThrow(NotFoundException);
    });

    it('throws BadRequestException for closed session', async () => {
      sessionRepo.findOne.mockResolvedValue(
        makeSession({ status: VotingStatus.CLOSED })
      );
      await expect(
        service.addCandidate('session-1', 'user-1', { supplierName: 'X' })
      ).rejects.toThrow(BadRequestException);
    });

    it('throws BadRequestException for expired session (closesAt in past)', async () => {
      sessionRepo.findOne.mockResolvedValue(
        makeSession({ closesAt: new Date(Date.now() - 1000) })
      );
      await expect(
        service.addCandidate('session-1', 'user-1', { supplierName: 'X' })
      ).rejects.toThrow(BadRequestException);
    });
  });

  // ─── castVote ──────────────────────────────────────────────────────────────

  describe('castVote', () => {
    it('casts a new vote successfully', async () => {
      const session = makeSession();
      const candidate = makeCandidate({ id: 'candidate-1', votingSessionId: 'session-1' });
      sessionRepo.findOne.mockResolvedValue(session);
      candidateRepo.findOne.mockResolvedValue(candidate);
      dataSource._manager.findOne.mockResolvedValue(null); // no existing vote
      dataSource._manager.create.mockReturnValue(makeVote());
      dataSource._manager.save.mockResolvedValue(makeVote());

      const result = await service.castVote('session-1', 'user-1', {
        candidateId: 'candidate-1',
        comment: 'Great price!',
      });

      expect(result.userId).toBe('user-1');
      expect(result.candidateId).toBe('candidate-1');
      expect(kafkaProducer.send).toHaveBeenCalledWith(
        'purchase.vote.cast',
        expect.objectContaining({
          sessionId: 'session-1',
          userId: 'user-1',
          candidateId: 'candidate-1',
        })
      );
    });

    it('changes vote when user already voted for a different candidate', async () => {
      const session = makeSession({ allowChangeVote: true });
      const newCandidate = makeCandidate({ id: 'candidate-2', votingSessionId: 'session-1' });
      const existingVote = makeVote({ candidateId: 'candidate-1', changedCount: 0 });

      sessionRepo.findOne.mockResolvedValue(session);
      candidateRepo.findOne.mockResolvedValue(newCandidate);
      dataSource._manager.findOne.mockResolvedValue(existingVote);
      dataSource._manager.save.mockImplementation((_: any, entity: any) =>
        Promise.resolve({ ...entity, candidateId: 'candidate-2', changedCount: 1 })
      );

      const result = await service.castVote('session-1', 'user-1', {
        candidateId: 'candidate-2',
      });

      expect(result.candidateId).toBe('candidate-2');
      expect(result.changedCount).toBe(1);
      expect(kafkaProducer.send).toHaveBeenCalledWith(
        'purchase.vote.changed',
        expect.objectContaining({
          oldCandidateId: 'candidate-1',
          newCandidateId: 'candidate-2',
        })
      );
    });

    it('accumulates changedCount on multiple vote changes', async () => {
      const session = makeSession({ allowChangeVote: true });
      const newCandidate = makeCandidate({ id: 'candidate-3', votingSessionId: 'session-1' });
      const existingVote = makeVote({ candidateId: 'candidate-2', changedCount: 2 });

      sessionRepo.findOne.mockResolvedValue(session);
      candidateRepo.findOne.mockResolvedValue(newCandidate);
      dataSource._manager.findOne.mockResolvedValue(existingVote);
      dataSource._manager.save.mockImplementation((_: any, entity: any) =>
        Promise.resolve({ ...entity, candidateId: 'candidate-3', changedCount: 3 })
      );

      const result = await service.castVote('session-1', 'user-1', {
        candidateId: 'candidate-3',
      });

      expect(result.changedCount).toBe(3);
    });

    it('throws BadRequestException when voting for same candidate twice', async () => {
      const session = makeSession({ allowChangeVote: true });
      const candidate = makeCandidate({ id: 'candidate-1' });
      const existingVote = makeVote({ candidateId: 'candidate-1' });

      sessionRepo.findOne.mockResolvedValue(session);
      candidateRepo.findOne.mockResolvedValue(candidate);
      dataSource._manager.findOne.mockResolvedValue(existingVote);

      await expect(
        service.castVote('session-1', 'user-1', { candidateId: 'candidate-1' })
      ).rejects.toThrow(BadRequestException);
    });

    it('throws ForbiddenException when changing vote is disallowed', async () => {
      const session = makeSession({ allowChangeVote: false });
      const existingVote = makeVote({ candidateId: 'candidate-1' });
      const newCandidate = makeCandidate({ id: 'candidate-2' });

      sessionRepo.findOne.mockResolvedValue(session);
      candidateRepo.findOne.mockResolvedValue(newCandidate);
      dataSource._manager.findOne.mockResolvedValue(existingVote);

      await expect(
        service.castVote('session-1', 'user-1', { candidateId: 'candidate-2' })
      ).rejects.toThrow(ForbiddenException);
    });

    it('throws NotFoundException when candidate does not belong to session', async () => {
      const session = makeSession();
      sessionRepo.findOne.mockResolvedValue(session);
      candidateRepo.findOne.mockResolvedValue(null); // candidate not found

      await expect(
        service.castVote('session-1', 'user-1', { candidateId: 'candidate-wrong' })
      ).rejects.toThrow(NotFoundException);
    });

    it('throws BadRequestException for expired session', async () => {
      sessionRepo.findOne.mockResolvedValue(
        makeSession({ closesAt: new Date(Date.now() - 1000) })
      );

      await expect(
        service.castVote('session-1', 'user-1', { candidateId: 'candidate-1' })
      ).rejects.toThrow(BadRequestException);
    });
  });

  // ─── closeSession ──────────────────────────────────────────────────────────

  describe('closeSession', () => {
    it('closes session and determines winner by vote count', async () => {
      const session = makeSession();
      const purchase = makePurchase({ status: PurchaseStatus.VOTING });
      const votes = [
        makeVote({ id: 'v1', candidateId: 'candidate-1', userId: 'user-1' }),
        makeVote({ id: 'v2', candidateId: 'candidate-1', userId: 'user-2' }),
        makeVote({ id: 'v3', candidateId: 'candidate-2', userId: 'user-3' }),
      ];

      sessionRepo.findOne.mockResolvedValue(session);
      purchaseRepo.findOne.mockResolvedValue(purchase);
      dataSource._manager.find.mockResolvedValue(votes);
      dataSource._manager.save.mockImplementation((_: any, entity: any) =>
        Promise.resolve({
          ...entity,
          status: VotingStatus.CLOSED,
          winnerCandidateId: 'candidate-1',
        })
      );
      dataSource._manager.update.mockResolvedValue(undefined);

      const result = await service.closeSession('session-1', 'organizer-1');

      expect(result.status).toBe(VotingStatus.CLOSED);
      expect(result.winnerCandidateId).toBe('candidate-1');
      expect(kafkaProducer.send).toHaveBeenCalledWith(
        'purchase.voting.closed',
        expect.objectContaining({
          winnerId: 'candidate-1',
          totalVotes: 3,
        })
      );
    });

    it('sets winnerCandidateId to null when no votes cast', async () => {
      const session = makeSession();
      const purchase = makePurchase({ status: PurchaseStatus.VOTING });

      sessionRepo.findOne.mockResolvedValue(session);
      purchaseRepo.findOne.mockResolvedValue(purchase);
      dataSource._manager.find.mockResolvedValue([]); // no votes
      dataSource._manager.save.mockImplementation((_: any, entity: any) =>
        Promise.resolve({
          ...entity,
          status: VotingStatus.CLOSED,
          winnerCandidateId: null,
        })
      );
      dataSource._manager.update.mockResolvedValue(undefined);

      const result = await service.closeSession('session-1', 'organizer-1');

      expect(result.winnerCandidateId).toBeNull();
      expect(dataSource._manager.update).toHaveBeenCalledWith(
        Purchase,
        'purchase-1',
        expect.objectContaining({ status: PurchaseStatus.CANCELLED })
      );
    });

    it('throws ForbiddenException when non-organizer tries to close', async () => {
      const session = makeSession();
      const purchase = makePurchase({ organizerId: 'organizer-1' });

      sessionRepo.findOne.mockResolvedValue(session);
      purchaseRepo.findOne.mockResolvedValue(purchase);

      await expect(
        service.closeSession('session-1', 'not-the-organizer')
      ).rejects.toThrow(ForbiddenException);
    });

    it('throws BadRequestException when session is already closed', async () => {
      sessionRepo.findOne.mockResolvedValue(
        makeSession({ status: VotingStatus.CLOSED })
      );

      await expect(
        service.closeSession('session-1', 'organizer-1')
      ).rejects.toThrow(BadRequestException);
    });
  });

  // ─── autoCloseExpiredSessions ──────────────────────────────────────────────

  describe('autoCloseExpiredSessions (scheduler)', () => {
    it('auto-closes sessions whose closesAt is in the past', async () => {
      const expiredSession = makeSession({
        closesAt: new Date(Date.now() - 3600000), // 1 hour ago
        votes: [makeVote({ candidateId: 'candidate-1' })],
        candidates: [makeCandidate()],
      });

      sessionRepo.find.mockResolvedValue([expiredSession]);
      dataSource._manager.find.mockResolvedValue([makeVote()]);
      dataSource._manager.save.mockImplementation((_: any, entity: any) =>
        Promise.resolve({ ...entity, status: VotingStatus.CLOSED, winnerCandidateId: 'candidate-1' })
      );
      dataSource._manager.update.mockResolvedValue(undefined);

      await service.autoCloseExpiredSessions();

      expect(dataSource.transaction).toHaveBeenCalled();
      expect(kafkaProducer.send).toHaveBeenCalledWith(
        'purchase.voting.closed',
        expect.any(Object)
      );
    });

    it('does NOT close sessions that are still open and not expired', async () => {
      const futureSession = makeSession({
        closesAt: new Date(Date.now() + 86400000 * 2), // 2 days in future
      });

      sessionRepo.find.mockResolvedValue([futureSession]);

      await service.autoCloseExpiredSessions();

      expect(dataSource.transaction).not.toHaveBeenCalled();
    });

    it('handles multiple expired sessions independently', async () => {
      const sessions = [
        makeSession({ id: 'session-a', closesAt: new Date(Date.now() - 1000) }),
        makeSession({ id: 'session-b', closesAt: new Date(Date.now() - 2000) }),
      ];

      sessionRepo.find.mockResolvedValue(sessions);
      dataSource._manager.find.mockResolvedValue([]);
      dataSource._manager.save.mockImplementation((_: any, entity: any) =>
        Promise.resolve({ ...entity, status: VotingStatus.CLOSED, winnerCandidateId: null })
      );
      dataSource._manager.update.mockResolvedValue(undefined);

      await service.autoCloseExpiredSessions();

      expect(dataSource.transaction).toHaveBeenCalledTimes(2);
    });
  });

  // ─── getSessionResults ─────────────────────────────────────────────────────

  describe('getSessionResults', () => {
    it('returns tally sorted by vote count descending', async () => {
      const candidate1 = makeCandidate({ id: 'c1', supplierName: 'A' });
      const candidate2 = makeCandidate({ id: 'c2', supplierName: 'B' });
      const session = makeSession({
        candidates: [candidate1, candidate2],
        votes: [
          makeVote({ id: 'v1', candidateId: 'c2', userId: 'u1' }),
          makeVote({ id: 'v2', candidateId: 'c2', userId: 'u2' }),
          makeVote({ id: 'v3', candidateId: 'c1', userId: 'u3' }),
        ],
      });

      sessionRepo.findOne.mockResolvedValue(session);

      const { tally } = await service.getSessionResults('session-1');

      expect(tally[0].candidate.id).toBe('c2');
      expect(tally[0].voteCount).toBe(2);
      expect(tally[1].candidate.id).toBe('c1');
      expect(tally[1].voteCount).toBe(1);
    });

    it('throws NotFoundException for non-existent session', async () => {
      sessionRepo.findOne.mockResolvedValue(null);

      await expect(
        service.getSessionResults('nonexistent')
      ).rejects.toThrow(NotFoundException);
    });

    it('returns null winner for open sessions', async () => {
      const session = makeSession({
        status: VotingStatus.OPEN,
        candidates: [makeCandidate()],
        votes: [makeVote()],
      });
      sessionRepo.findOne.mockResolvedValue(session);

      const { winner } = await service.getSessionResults('session-1');
      expect(winner).toBeNull();
    });

    // ── voted flag (issue #282) ───────────────────────────────────────────

    it('sets voted=true only on the candidate the requesting user voted for', async () => {
      const c1 = makeCandidate({ id: 'c1', supplierName: 'Alpha' });
      const c2 = makeCandidate({ id: 'c2', supplierName: 'Beta' });
      const session = makeSession({
        candidates: [c1, c2],
        votes: [
          makeVote({ id: 'v1', candidateId: 'c1', userId: 'user-42' }),
          makeVote({ id: 'v2', candidateId: 'c2', userId: 'user-99' }),
        ],
      });
      sessionRepo.findOne.mockResolvedValue(session);

      const { tally, currentUserCandidateId } = await service.getSessionResults('session-1', 'user-42');

      const c1Entry = tally.find((t) => t.candidate.id === 'c1');
      const c2Entry = tally.find((t) => t.candidate.id === 'c2');

      expect(c1Entry?.voted).toBe(true);   // user-42 voted for c1
      expect(c2Entry?.voted).toBe(false);  // user-42 did NOT vote for c2
      expect(currentUserCandidateId).toBe('c1');
    });

    it('sets voted=false for all candidates when userId is null (unauthenticated)', async () => {
      const c1 = makeCandidate({ id: 'c1', supplierName: 'Alpha' });
      const session = makeSession({
        candidates: [c1],
        votes: [makeVote({ candidateId: 'c1', userId: 'someone-else' })],
      });
      sessionRepo.findOne.mockResolvedValue(session);

      const { tally, currentUserCandidateId } = await service.getSessionResults('session-1', null);

      expect(tally[0].voted).toBe(false);
      expect(currentUserCandidateId).toBeNull();
    });

    it('sets voted=false for all candidates when user has not voted', async () => {
      const c1 = makeCandidate({ id: 'c1', supplierName: 'Alpha' });
      const c2 = makeCandidate({ id: 'c2', supplierName: 'Beta' });
      const session = makeSession({
        candidates: [c1, c2],
        votes: [makeVote({ candidateId: 'c1', userId: 'other-user' })],
      });
      sessionRepo.findOne.mockResolvedValue(session);

      const { tally, currentUserCandidateId } = await service.getSessionResults('session-1', 'new-user-no-vote');

      expect(tally.every((t) => t.voted === false)).toBe(true);
      expect(currentUserCandidateId).toBeNull();
    });

    it('does not perform extra DB queries for voted flag (no N+1)', async () => {
      // The votes are loaded once with the session via relations; no extra findOne calls.
      const candidates = Array.from({ length: 50 }, (_, i) =>
        makeCandidate({ id: `c${i}`, supplierName: `Supplier ${i}` }),
      );
      const votes = candidates.map((c, i) =>
        makeVote({ id: `v${i}`, candidateId: c.id, userId: `user-${i}` }),
      );
      const session = makeSession({ candidates, votes });
      sessionRepo.findOne.mockResolvedValue(session);

      await service.getSessionResults('session-1', 'user-5');

      // Only one findOne call for the session itself — no additional queries
      expect(sessionRepo.findOne).toHaveBeenCalledTimes(1);
    });
  });
});

/**
 * Tests for issue #214 changes in purchase-service:
 * - Purchases are created with ACTIVE status by default
 * - Active purchases can be updated
 * - Active purchases can start voting
 */

import { Test, TestingModule } from '@nestjs/testing';
import { getRepositoryToken } from '@nestjs/typeorm';
import { DataSource } from 'typeorm';
import { BadRequestException, ForbiddenException, NotFoundException } from '@nestjs/common';

import { PurchasesService, CreatePurchaseDto } from '../../services/purchase-service/src/purchases/purchases.service';
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
    status: PurchaseStatus.ACTIVE,
    minParticipants: 2,
    maxParticipants: null,
    targetAmount: null,
    currency: 'RUB',
    category: null,
    commissionPercent: 0,
    escrowRequired: false,
    escrowThreshold: 1000000,
    deadlineAt: null,
    closedAt: null,
    metadata: {},
    votingSession: null,
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
    findAndCount: jest.fn(),
    create: jest.fn((dto: any) => dto),
    save: jest.fn((entity: any) => Promise.resolve({ ...entity, id: entity.id || 'new-id' })),
    update: jest.fn().mockResolvedValue(undefined),
    createQueryBuilder: jest.fn(() => ({
      where: jest.fn().mockReturnThis(),
      andWhere: jest.fn().mockReturnThis(),
      getCount: jest.fn().mockResolvedValue(0),
    })),
  };
}

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

// ─── PurchasesService Tests ───────────────────────────────────────────────────

describe('PurchasesService', () => {
  let service: PurchasesService;
  let purchaseRepo: ReturnType<typeof mockRepo>;
  let kafkaProducer: jest.Mocked<KafkaProducer>;

  beforeEach(async () => {
    purchaseRepo = mockRepo();
    kafkaProducer = { send: jest.fn().mockResolvedValue(undefined) } as any;

    const module: TestingModule = await Test.createTestingModule({
      providers: [
        PurchasesService,
        { provide: getRepositoryToken(Purchase), useValue: purchaseRepo },
        { provide: KafkaProducer, useValue: kafkaProducer },
      ],
    }).compile();

    service = module.get<PurchasesService>(PurchasesService);
  });

  afterEach(() => {
    jest.clearAllMocks();
  });

  // ─── create ────────────────────────────────────────────────────────────────

  describe('create', () => {
    const baseDto: CreatePurchaseDto = {
      title: 'Group Buy Test',
      organizerId: 'organizer-1',
    };

    it('creates a purchase with ACTIVE status by default', async () => {
      const saved = makePurchase({ status: PurchaseStatus.ACTIVE });
      purchaseRepo.save.mockResolvedValue(saved);

      const result = await service.create(baseDto);

      expect(purchaseRepo.create).toHaveBeenCalledWith(
        expect.objectContaining({ status: PurchaseStatus.ACTIVE })
      );
      expect(result.status).toBe(PurchaseStatus.ACTIVE);
    });

    it('emits purchase.created Kafka event after creation', async () => {
      const saved = makePurchase();
      purchaseRepo.save.mockResolvedValue(saved);

      await service.create(baseDto);

      expect(kafkaProducer.send).toHaveBeenCalledWith(
        'purchase.created',
        expect.objectContaining({ purchaseId: saved.id, organizerId: saved.organizerId })
      );
    });

    it('throws BadRequestException if organizer quota is exceeded', async () => {
      purchaseRepo.createQueryBuilder.mockReturnValue({
        where: jest.fn().mockReturnThis(),
        andWhere: jest.fn().mockReturnThis(),
        getCount: jest.fn().mockResolvedValue(50),
      });

      await expect(service.create(baseDto)).rejects.toThrow(BadRequestException);
    });

    it('includes ACTIVE status in quota count statuses', async () => {
      const qb = {
        where: jest.fn().mockReturnThis(),
        andWhere: jest.fn().mockReturnThis(),
        getCount: jest.fn().mockResolvedValue(0),
      };
      purchaseRepo.createQueryBuilder.mockReturnValue(qb);
      purchaseRepo.save.mockResolvedValue(makePurchase());

      await service.create(baseDto);

      // andWhere for statuses should include ACTIVE
      expect(qb.andWhere).toHaveBeenCalledWith(
        'p.status IN (:...statuses)',
        expect.objectContaining({
          statuses: expect.arrayContaining([PurchaseStatus.ACTIVE]),
        })
      );
    });
  });

  // ─── update ────────────────────────────────────────────────────────────────

  describe('update', () => {
    it('allows updating an ACTIVE purchase', async () => {
      const purchase = makePurchase({ status: PurchaseStatus.ACTIVE });
      purchaseRepo.findOne.mockResolvedValue(purchase);
      purchaseRepo.save.mockResolvedValue({ ...purchase, title: 'Updated Title' });

      const result = await service.update('purchase-1', 'organizer-1', { title: 'Updated Title' });

      expect(result.title).toBe('Updated Title');
    });

    it('allows updating a DRAFT purchase', async () => {
      const purchase = makePurchase({ status: PurchaseStatus.DRAFT });
      purchaseRepo.findOne.mockResolvedValue(purchase);
      purchaseRepo.save.mockResolvedValue({ ...purchase, title: 'Updated Title' });

      const result = await service.update('purchase-1', 'organizer-1', { title: 'Updated Title' });

      expect(result.title).toBe('Updated Title');
    });

    it('throws BadRequestException when updating a VOTING purchase', async () => {
      const purchase = makePurchase({ status: PurchaseStatus.VOTING });
      purchaseRepo.findOne.mockResolvedValue(purchase);

      await expect(
        service.update('purchase-1', 'organizer-1', { title: 'New Title' })
      ).rejects.toThrow(BadRequestException);
    });

    it('throws ForbiddenException when non-organizer tries to update', async () => {
      const purchase = makePurchase({ status: PurchaseStatus.ACTIVE });
      purchaseRepo.findOne.mockResolvedValue(purchase);

      await expect(
        service.update('purchase-1', 'other-user', { title: 'Hijack' })
      ).rejects.toThrow(ForbiddenException);
    });
  });
});

// ─── VotingService: createSession with ACTIVE purchase ───────────────────────

describe('VotingService - createSession with ACTIVE purchase', () => {
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

  it('allows starting a voting session for an ACTIVE purchase', async () => {
    const purchase = makePurchase({ status: PurchaseStatus.ACTIVE });
    purchaseRepo.findOne.mockResolvedValue(purchase);
    dataSource._manager.save.mockImplementation((_: any, entity: any) =>
      Promise.resolve({ ...entity, id: 'session-new' })
    );

    const closesAt = new Date(Date.now() + 86400000 * 5);
    const result = await service.createSession({
      purchaseId: 'purchase-1',
      closesAt,
    });

    expect(result.id).toBe('session-new');
    expect(dataSource._manager.update).toHaveBeenCalledWith(
      Purchase,
      'purchase-1',
      expect.objectContaining({ status: PurchaseStatus.VOTING })
    );
  });

  it('throws BadRequestException when starting voting for a VOTING purchase', async () => {
    const purchase = makePurchase({ status: PurchaseStatus.VOTING });
    purchaseRepo.findOne.mockResolvedValue(purchase);

    const closesAt = new Date(Date.now() + 86400000 * 5);
    await expect(
      service.createSession({ purchaseId: 'purchase-1', closesAt })
    ).rejects.toThrow(BadRequestException);
  });

  it('throws BadRequestException when starting voting for a CANCELLED purchase', async () => {
    const purchase = makePurchase({ status: PurchaseStatus.CANCELLED });
    purchaseRepo.findOne.mockResolvedValue(purchase);

    const closesAt = new Date(Date.now() + 86400000 * 5);
    await expect(
      service.createSession({ purchaseId: 'purchase-1', closesAt })
    ).rejects.toThrow(BadRequestException);
  });
});

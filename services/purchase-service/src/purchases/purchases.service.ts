import {
  Injectable,
  NotFoundException,
  ForbiddenException,
  BadRequestException,
  Logger,
} from '@nestjs/common';
import { InjectRepository } from '@nestjs/typeorm';
import { Repository } from 'typeorm';
import { Purchase, PurchaseStatus } from './purchases.entity';
import { PurchaseUser, PurchaseUserRole } from './purchase-user.entity';
import { KafkaProducer } from '../kafka/kafka.producer';

const MAX_ACTIVE_PURCHASES = 50;
const WARN_ACTIVE_PURCHASES = 40;

export interface CreatePurchaseDto {
  title: string;
  description?: string;
  organizerId: string;
  minParticipants?: number;
  maxParticipants?: number;
  targetAmount?: number;
  currency?: string;
  category?: string;
  deadlineAt?: Date;
  commissionPercent?: number;
  escrowThreshold?: number;
}

@Injectable()
export class PurchasesService {
  private readonly logger = new Logger(PurchasesService.name);

  constructor(
    @InjectRepository(Purchase)
    private readonly purchaseRepo: Repository<Purchase>,
    @InjectRepository(PurchaseUser)
    private readonly purchaseUserRepo: Repository<PurchaseUser>,
    private readonly kafkaProducer: KafkaProducer,
  ) {}

  private validateCommission(commissionPercent: number): void {
    if (commissionPercent < 0 || commissionPercent > 10) {
      throw new BadRequestException('Commission percent must be between 0 and 10');
    }
    // Step of 0.5: multiply by 2 and check it's an integer
    if ((commissionPercent * 2) % 1 !== 0) {
      throw new BadRequestException('Commission percent must be in steps of 0.5');
    }
  }

  private computeEscrowRequired(targetAmount: number | null, escrowThreshold: number): boolean {
    if (targetAmount == null) return false;
    return targetAmount > escrowThreshold;
  }

  private async checkOrganizerQuota(organizerId: string): Promise<void> {
    const activeStatuses = [
      PurchaseStatus.DRAFT,
      PurchaseStatus.ACTIVE,
      PurchaseStatus.VOTING,
      PurchaseStatus.APPROVED,
      PurchaseStatus.PAYMENT_PENDING,
    ];
    const activeCount = await this.purchaseRepo
      .createQueryBuilder('p')
      .where('p.organizer_id = :organizerId', { organizerId })
      .andWhere('p.status IN (:...statuses)', { statuses: activeStatuses })
      .getCount();

    if (activeCount >= MAX_ACTIVE_PURCHASES) {
      throw new BadRequestException(
        `Organizer has reached the maximum of ${MAX_ACTIVE_PURCHASES} active purchases`,
      );
    }
    if (activeCount >= WARN_ACTIVE_PURCHASES) {
      this.logger.warn(
        `Organizer ${organizerId} has ${activeCount} active purchases (limit: ${MAX_ACTIVE_PURCHASES})`,
      );
    }
  }

  async create(dto: CreatePurchaseDto): Promise<Purchase> {
    const commissionPercent = dto.commissionPercent ?? 0;
    this.validateCommission(commissionPercent);

    await this.checkOrganizerQuota(dto.organizerId);

    const escrowThreshold = dto.escrowThreshold ?? 1000000;
    const escrowRequired = this.computeEscrowRequired(dto.targetAmount ?? null, escrowThreshold);

    const purchase = this.purchaseRepo.create({
      title: dto.title,
      description: dto.description ?? null,
      organizerId: dto.organizerId,
      minParticipants: dto.minParticipants ?? 2,
      maxParticipants: dto.maxParticipants ?? null,
      targetAmount: dto.targetAmount ?? null,
      currency: dto.currency ?? 'RUB',
      category: dto.category ?? null,
      deadlineAt: dto.deadlineAt ?? null,
      commissionPercent,
      escrowRequired,
      escrowThreshold,
      status: PurchaseStatus.ACTIVE,
    });
    const saved = await this.purchaseRepo.save(purchase);

    await this.kafkaProducer.send('purchase.created', {
      purchaseId: saved.id,
      organizerId: saved.organizerId,
      title: saved.title,
      commissionPercent: saved.commissionPercent,
      escrowRequired: saved.escrowRequired,
    });

    return saved;
  }

  async findAll(page = 1, limit = 20): Promise<{ data: Purchase[]; total: number }> {
    const [data, total] = await this.purchaseRepo.findAndCount({
      order: { createdAt: 'DESC' },
      skip: (page - 1) * limit,
      take: limit,
    });
    return { data, total };
  }

  async findById(id: string): Promise<Purchase> {
    const purchase = await this.purchaseRepo.findOne({
      where: { id },
      relations: ['votingSession'],
    });
    if (!purchase) throw new NotFoundException('Purchase not found');
    return purchase;
  }

  /** Returns the role of a user for a purchase, or null if they have no access. */
  async getUserRole(purchaseId: string, userId: string): Promise<PurchaseUserRole | null> {
    const purchase = await this.purchaseRepo.findOne({ where: { id: purchaseId } });
    if (!purchase) return null;
    if (purchase.organizerId === userId) return PurchaseUserRole.OWNER;
    const pu = await this.purchaseUserRepo.findOne({ where: { purchaseId, userId } });
    return pu ? pu.role : null;
  }

  /** Adds a user as editor to a purchase. Only the owner can do this. */
  async addEditor(
    purchaseId: string,
    requesterId: string,
    targetUserId: string,
  ): Promise<PurchaseUser> {
    const purchase = await this.findById(purchaseId);
    if (purchase.organizerId !== requesterId) {
      throw new ForbiddenException('Only the owner can add editors');
    }
    if (targetUserId === requesterId) {
      throw new BadRequestException('Owner cannot add themselves as editor');
    }

    const existing = await this.purchaseUserRepo.findOne({
      where: { purchaseId, userId: targetUserId },
    });
    if (existing) {
      return existing; // Already an editor
    }

    const pu = this.purchaseUserRepo.create({
      purchaseId,
      userId: targetUserId,
      role: PurchaseUserRole.EDITOR,
      invitedBy: requesterId,
    });
    const saved = await this.purchaseUserRepo.save(pu);

    await this.kafkaProducer.send('purchase.editor.added', {
      purchaseId,
      userId: targetUserId,
      invitedBy: requesterId,
    });

    return saved;
  }

  /** Removes an editor from a purchase. Only the owner can do this. */
  async removeEditor(purchaseId: string, requesterId: string, targetUserId: string): Promise<void> {
    const purchase = await this.findById(purchaseId);
    if (purchase.organizerId !== requesterId) {
      throw new ForbiddenException('Only the owner can remove editors');
    }

    const existing = await this.purchaseUserRepo.findOne({
      where: { purchaseId, userId: targetUserId },
    });
    if (!existing) {
      throw new NotFoundException('Editor not found for this purchase');
    }
    await this.purchaseUserRepo.remove(existing);

    await this.kafkaProducer.send('purchase.editor.removed', {
      purchaseId,
      userId: targetUserId,
      removedBy: requesterId,
    });
  }

  /** Lists all editors of a purchase. */
  async listEditors(purchaseId: string): Promise<PurchaseUser[]> {
    await this.findById(purchaseId); // Ensure purchase exists
    return this.purchaseUserRepo.find({ where: { purchaseId } });
  }

  /**
   * Invite a user to participate in a purchase.
   * Any existing participant (including the organizer) can invite another user.
   * The invited user is recorded as a PARTICIPANT so the notification service can
   * alert them and they can confirm their participation.
   */
  async inviteParticipant(
    purchaseId: string,
    requesterId: string,
    targetUserId: string,
  ): Promise<PurchaseUser> {
    const purchase = await this.findById(purchaseId);

    if (purchase.status !== PurchaseStatus.ACTIVE) {
      throw new BadRequestException('Can only invite participants to active purchases');
    }
    if (targetUserId === requesterId) {
      throw new BadRequestException('Cannot invite yourself');
    }

    // Only the organizer or an existing participant/editor can send invites
    const isOrganizer = purchase.organizerId === requesterId;
    const requesterEntry = isOrganizer
      ? null
      : await this.purchaseUserRepo.findOne({ where: { purchaseId, userId: requesterId } });
    if (!isOrganizer && !requesterEntry) {
      throw new ForbiddenException('Only existing participants or the organizer can invite users');
    }

    // Idempotent: return existing record if already invited/participating
    const existing = await this.purchaseUserRepo.findOne({
      where: { purchaseId, userId: targetUserId },
    });
    if (existing) {
      return existing;
    }

    const pu = this.purchaseUserRepo.create({
      purchaseId,
      userId: targetUserId,
      role: PurchaseUserRole.PARTICIPANT,
      invitedBy: requesterId,
    });
    const saved = await this.purchaseUserRepo.save(pu);

    await this.kafkaProducer.send('purchase.participant.invited', {
      purchaseId,
      userId: targetUserId,
      invitedBy: requesterId,
    });

    return saved;
  }

  async update(
    id: string,
    requesterId: string,
    updates: Partial<CreatePurchaseDto>,
  ): Promise<Purchase> {
    const purchase = await this.findById(id);
    const role = await this.getUserRole(id, requesterId);
    if (role === null) {
      throw new ForbiddenException('Only the organizer or an editor can update this purchase');
    }
    // Editors cannot change commission or escrow — owner-only fields
    if (role === PurchaseUserRole.EDITOR) {
      if (updates.commissionPercent != null || updates.escrowThreshold != null) {
        throw new ForbiddenException('Editors cannot modify commission or escrow settings');
      }
    }
    if (purchase.status !== PurchaseStatus.DRAFT && purchase.status !== PurchaseStatus.ACTIVE) {
      throw new BadRequestException('Can only update draft or active purchases');
    }

    if (updates.commissionPercent != null) {
      this.validateCommission(updates.commissionPercent);
    }

    Object.assign(purchase, updates);

    // Recompute escrow if targetAmount or escrowThreshold changed
    const escrowThreshold = purchase.escrowThreshold;
    purchase.escrowRequired = this.computeEscrowRequired(purchase.targetAmount, escrowThreshold);

    return this.purchaseRepo.save(purchase);
  }

  async cancel(id: string, requesterId: string): Promise<Purchase> {
    const purchase = await this.findById(id);
    // Only the owner (organizer) can cancel; editors cannot
    if (purchase.organizerId !== requesterId) {
      throw new ForbiddenException('Only the organizer can cancel this purchase');
    }
    if ([PurchaseStatus.COMPLETED, PurchaseStatus.CANCELLED].includes(purchase.status)) {
      throw new BadRequestException('Purchase is already completed or cancelled');
    }
    purchase.status = PurchaseStatus.CANCELLED;
    purchase.closedAt = new Date();
    const saved = await this.purchaseRepo.save(purchase);

    await this.kafkaProducer.send('purchase.cancelled', {
      purchaseId: id,
      organizerId: requesterId,
    });

    // Emit commission calculated event when purchase stops
    if (saved.commissionPercent > 0 && saved.targetAmount != null) {
      const commissionAmount = (saved.targetAmount * saved.commissionPercent) / 100;
      await this.kafkaProducer.send('purchase.commission.calculated', {
        purchaseId: saved.id,
        organizerId: saved.organizerId,
        targetAmount: saved.targetAmount,
        commissionPercent: saved.commissionPercent,
        commissionAmount,
        currency: saved.currency,
      });
    }

    return saved;
  }

  async emitCommissionOnComplete(purchaseId: string): Promise<void> {
    const purchase = await this.findById(purchaseId);
    if (purchase.commissionPercent > 0 && purchase.targetAmount != null) {
      const commissionAmount = (purchase.targetAmount * purchase.commissionPercent) / 100;
      await this.kafkaProducer.send('purchase.commission.calculated', {
        purchaseId: purchase.id,
        organizerId: purchase.organizerId,
        targetAmount: purchase.targetAmount,
        commissionPercent: purchase.commissionPercent,
        commissionAmount,
        currency: purchase.currency,
      });
    }
  }
}

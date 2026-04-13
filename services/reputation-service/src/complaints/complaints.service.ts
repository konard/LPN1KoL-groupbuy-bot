import {
  Injectable,
  BadRequestException,
  NotFoundException,
  Logger,
} from '@nestjs/common';
import { InjectRepository } from '@nestjs/typeorm';
import { Repository, LessThan, In } from 'typeorm';
import { Complaint, ComplaintType, ComplaintStatus } from './complaints.entity';

export interface AutoBlockResult {
  shouldBlock: boolean;
  reason: string | null;
  distinctReporters: number;
  distinctTypes: number;
  unansweredCount: number;
}

@Injectable()
export class ComplaintsService {
  private readonly logger = new Logger(ComplaintsService.name);

  constructor(
    @InjectRepository(Complaint)
    private readonly complaintRepository: Repository<Complaint>,
  ) {}

  async fileComplaint(params: {
    reporterId: string;
    targetId: string;
    purchaseId?: string;
    type: ComplaintType;
    description: string;
    evidenceUrls?: string[];
  }): Promise<Complaint> {
    if (params.reporterId === params.targetId) {
      throw new BadRequestException('Cannot file a complaint against yourself');
    }

    if (!params.description || params.description.trim().length < 10) {
      throw new BadRequestException('Description must be at least 10 characters');
    }

    const complaint = this.complaintRepository.create({
      reporterId: params.reporterId,
      targetId: params.targetId,
      purchaseId: params.purchaseId ?? null,
      type: params.type,
      description: params.description.trim(),
      evidenceUrls: params.evidenceUrls ?? null,
      status: ComplaintStatus.PENDING,
      resolution: null,
      adminId: null,
      resolvedAt: null,
    });

    const saved = await this.complaintRepository.save(complaint);

    this.logger.log(
      `Complaint filed: reporter=${params.reporterId} target=${params.targetId} type=${params.type}`,
    );

    const autoBlock = await this.checkAutoBlock(params.targetId);
    if (autoBlock.shouldBlock) {
      this.logger.warn(
        `Auto-block triggered for user ${params.targetId}: ${autoBlock.reason}`,
      );
    }

    return saved;
  }

  async getComplaints(options?: {
    status?: ComplaintStatus;
    limit?: number;
    offset?: number;
  }): Promise<{ complaints: Complaint[]; total: number }> {
    const queryBuilder = this.complaintRepository
      .createQueryBuilder('complaint')
      .orderBy('complaint.created_at', 'DESC');

    if (options?.status) {
      queryBuilder.where('complaint.status = :status', { status: options.status });
    }

    const total = await queryBuilder.getCount();

    queryBuilder
      .limit(options?.limit ?? 50)
      .offset(options?.offset ?? 0);

    const complaints = await queryBuilder.getMany();

    return { complaints, total };
  }

  async getComplaintsForUser(
    userId: string,
    options?: { limit?: number; offset?: number },
  ): Promise<{ complaints: Complaint[]; total: number }> {
    const [complaints, total] = await this.complaintRepository.findAndCount({
      where: { targetId: userId },
      order: { createdAt: 'DESC' },
      take: options?.limit ?? 50,
      skip: options?.offset ?? 0,
    });

    return { complaints, total };
  }

  async resolveComplaint(
    complaintId: string,
    params: {
      adminId: string;
      status: ComplaintStatus.RESOLVED | ComplaintStatus.REJECTED;
      resolution: string;
    },
  ): Promise<Complaint> {
    const complaint = await this.complaintRepository.findOne({
      where: { id: complaintId },
    });

    if (!complaint) {
      throw new NotFoundException('Complaint not found');
    }

    if (
      complaint.status === ComplaintStatus.RESOLVED ||
      complaint.status === ComplaintStatus.REJECTED
    ) {
      throw new BadRequestException('Complaint has already been resolved');
    }

    complaint.adminId = params.adminId;
    complaint.status = params.status;
    complaint.resolution = params.resolution;
    complaint.resolvedAt = new Date();

    const saved = await this.complaintRepository.save(complaint);

    this.logger.log(
      `Complaint ${complaintId} resolved by admin ${params.adminId}: status=${params.status}`,
    );

    return saved;
  }

  async checkAutoBlock(targetId: string): Promise<AutoBlockResult> {
    const seventyTwoHoursAgo = new Date();
    seventyTwoHoursAgo.setHours(seventyTwoHoursAgo.getHours() - 72);

    const pendingComplaints = await this.complaintRepository.find({
      where: {
        targetId,
        status: In([ComplaintStatus.PENDING, ComplaintStatus.INVESTIGATING]),
      },
    });

    const unansweredComplaints = pendingComplaints.filter(
      (c) => c.createdAt <= seventyTwoHoursAgo,
    );

    const distinctReporters = new Set(
      pendingComplaints.map((c) => c.reporterId),
    ).size;

    const distinctTypes = new Set(
      pendingComplaints.map((c) => c.type),
    ).size;

    const shouldBlock =
      distinctReporters >= 3 &&
      distinctTypes >= 2 &&
      unansweredComplaints.length > 0;

    const reason = shouldBlock
      ? `Auto-block: ${distinctReporters} distinct reporters, ${distinctTypes} distinct complaint types, ${unansweredComplaints.length} unanswered complaints older than 72h`
      : null;

    return {
      shouldBlock,
      reason,
      distinctReporters,
      distinctTypes,
      unansweredCount: unansweredComplaints.length,
    };
  }
}

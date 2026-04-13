import {
  Injectable,
  BadRequestException,
  NotFoundException,
  ConflictException,
  Logger,
} from '@nestjs/common';
import { InjectRepository } from '@nestjs/typeorm';
import { Repository } from 'typeorm';
import { Review, ReviewRole, ReviewCategories } from './reviews.entity';

export interface ReputationScore {
  userId: string;
  averageRating: number;
  totalReviews: number;
  categories: {
    reliability: number | null;
    speed: number | null;
    quality: number | null;
    timeliness: number | null;
  };
}

export interface UserLimits {
  maxActivePurchases: number;
  searchPriorityBoost: number;
  escrowEligible: boolean;
}

@Injectable()
export class ReviewsService {
  private readonly logger = new Logger(ReviewsService.name);

  constructor(
    @InjectRepository(Review)
    private readonly reviewRepository: Repository<Review>,
  ) {}

  async createReview(params: {
    reviewerId: string;
    targetId: string;
    purchaseId: string;
    role: ReviewRole;
    rating: number;
    categories?: ReviewCategories;
    comment?: string;
    expiresAt: Date;
  }): Promise<Review> {
    if (params.rating < 1 || params.rating > 5 || !Number.isInteger(params.rating)) {
      throw new BadRequestException('Rating must be an integer between 1 and 5');
    }

    if (params.reviewerId === params.targetId) {
      throw new BadRequestException('Cannot review yourself');
    }

    if (new Date() > params.expiresAt) {
      throw new BadRequestException('Review window has expired (14-day limit after purchase completion)');
    }

    if (params.categories) {
      const categoryValues = Object.values(params.categories).filter(
        (v) => v !== undefined && v !== null,
      );
      for (const val of categoryValues) {
        if (val < 1 || val > 5 || !Number.isInteger(val)) {
          throw new BadRequestException('Category ratings must be integers between 1 and 5');
        }
      }
    }

    const existing = await this.reviewRepository.findOne({
      where: {
        reviewerId: params.reviewerId,
        purchaseId: params.purchaseId,
      },
    });

    if (existing) {
      throw new ConflictException('You have already reviewed this purchase');
    }

    const review = this.reviewRepository.create({
      reviewerId: params.reviewerId,
      targetId: params.targetId,
      purchaseId: params.purchaseId,
      role: params.role,
      rating: params.rating,
      categories: params.categories ?? null,
      comment: params.comment ?? null,
      expiresAt: params.expiresAt,
    });

    const saved = await this.reviewRepository.save(review);
    this.logger.log(
      `Review created: reviewer=${params.reviewerId} target=${params.targetId} rating=${params.rating}`,
    );
    return saved;
  }

  async getReviewsForUser(
    userId: string,
    options?: { role?: ReviewRole; limit?: number; offset?: number },
  ): Promise<{ reviews: Review[]; total: number; averageRating: number }> {
    const queryBuilder = this.reviewRepository
      .createQueryBuilder('review')
      .where('review.target_id = :userId', { userId });

    if (options?.role) {
      queryBuilder.andWhere('review.role = :role', { role: options.role });
    }

    const total = await queryBuilder.getCount();

    // Compute average only over the filtered set (respect role filter when provided)
    const avgQueryBuilder = this.reviewRepository
      .createQueryBuilder('review')
      .select('AVG(review.rating)', 'avg')
      .where('review.target_id = :userId', { userId });
    if (options?.role) {
      avgQueryBuilder.andWhere('review.role = :role', { role: options.role });
    }
    const avgResult = await avgQueryBuilder.getRawOne();

    const averageRating = avgResult?.avg ? parseFloat(parseFloat(avgResult.avg).toFixed(2)) : 0;

    queryBuilder
      .orderBy('review.created_at', 'DESC')
      .limit(options?.limit ?? 20)
      .offset(options?.offset ?? 0);

    const reviews = await queryBuilder.getMany();

    return { reviews, total, averageRating };
  }

  /**
   * Returns a breakdown of a user's reputation per role (buyer, organizer, supplier).
   * Each entry contains the average rating and total reviews for that specific role.
   */
  async getRatingsByRole(userId: string): Promise<{
    buyer: { averageRating: number; totalReviews: number };
    organizer: { averageRating: number; totalReviews: number };
    supplier: { averageRating: number; totalReviews: number };
  }> {
    const rows: Array<{ role: string; avg: string; count: string }> = await this.reviewRepository
      .createQueryBuilder('review')
      .select('review.role', 'role')
      .addSelect('AVG(review.rating)', 'avg')
      .addSelect('COUNT(*)', 'count')
      .where('review.target_id = :userId', { userId })
      .groupBy('review.role')
      .getRawMany();

    const build = (role: string) => {
      const row = rows.find((r) => r.role === role);
      return {
        averageRating: row?.avg ? parseFloat(parseFloat(row.avg).toFixed(2)) : 0,
        totalReviews: row?.count ? parseInt(row.count, 10) : 0,
      };
    };

    return {
      buyer: build(ReviewRole.BUYER),
      organizer: build(ReviewRole.ORGANIZER),
      supplier: build(ReviewRole.SUPPLIER),
    };
  }

  async getReputationScore(userId: string): Promise<ReputationScore> {
    const reviews = await this.reviewRepository.find({
      where: { targetId: userId },
    });

    if (reviews.length === 0) {
      return {
        userId,
        averageRating: 0,
        totalReviews: 0,
        categories: {
          reliability: null,
          speed: null,
          quality: null,
          timeliness: null,
        },
      };
    }

    const totalRating = reviews.reduce((sum, r) => sum + r.rating, 0);
    const averageRating = parseFloat((totalRating / reviews.length).toFixed(2));

    const categoryAverages = this.computeCategoryAverages(reviews);

    return {
      userId,
      averageRating,
      totalReviews: reviews.length,
      categories: categoryAverages,
    };
  }

  getUserLimits(reputation: ReputationScore): UserLimits {
    const { averageRating, totalReviews } = reputation;

    let maxActivePurchases: number;
    if (totalReviews === 0) {
      maxActivePurchases = 3;
    } else if (averageRating >= 4.5 && totalReviews >= 20) {
      maxActivePurchases = 15;
    } else if (averageRating >= 4.0 && totalReviews >= 10) {
      maxActivePurchases = 10;
    } else if (averageRating >= 3.5 && totalReviews >= 5) {
      maxActivePurchases = 7;
    } else if (averageRating >= 3.0) {
      maxActivePurchases = 5;
    } else {
      maxActivePurchases = 2;
    }

    let searchPriorityBoost: number;
    if (averageRating >= 4.5 && totalReviews >= 10) {
      searchPriorityBoost = 3;
    } else if (averageRating >= 4.0 && totalReviews >= 5) {
      searchPriorityBoost = 2;
    } else if (averageRating >= 3.5) {
      searchPriorityBoost = 1;
    } else {
      searchPriorityBoost = 0;
    }

    const escrowEligible = averageRating >= 4.0 && totalReviews >= 10;

    return { maxActivePurchases, searchPriorityBoost, escrowEligible };
  }

  private computeCategoryAverages(reviews: Review[]): {
    reliability: number | null;
    speed: number | null;
    quality: number | null;
    timeliness: number | null;
  } {
    const sums: Record<string, { total: number; count: number }> = {
      reliability: { total: 0, count: 0 },
      speed: { total: 0, count: 0 },
      quality: { total: 0, count: 0 },
      timeliness: { total: 0, count: 0 },
    };

    for (const review of reviews) {
      if (!review.categories) continue;
      for (const key of Object.keys(sums)) {
        const val = (review.categories as Record<string, number | undefined>)[key];
        if (val !== undefined && val !== null) {
          sums[key].total += val;
          sums[key].count += 1;
        }
      }
    }

    const result: Record<string, number | null> = {};
    for (const key of Object.keys(sums)) {
      result[key] =
        sums[key].count > 0
          ? parseFloat((sums[key].total / sums[key].count).toFixed(2))
          : null;
    }

    return result as {
      reliability: number | null;
      speed: number | null;
      quality: number | null;
      timeliness: number | null;
    };
  }
}

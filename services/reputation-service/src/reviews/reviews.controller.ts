import {
  Controller,
  Post,
  Get,
  Body,
  Param,
  Query,
  HttpCode,
  HttpStatus,
  ParseUUIDPipe,
} from '@nestjs/common';
import {
  IsUUID,
  IsEnum,
  IsInt,
  Min,
  Max,
  IsOptional,
  IsString,
  IsObject,
  ValidateNested,
} from 'class-validator';
import { Type } from 'class-transformer';
import { ReviewsService } from './reviews.service';
import { ReviewRole } from './reviews.entity';

class CategoryRatingsDto {
  @IsOptional()
  @IsInt()
  @Min(1)
  @Max(5)
  reliability?: number;

  @IsOptional()
  @IsInt()
  @Min(1)
  @Max(5)
  speed?: number;

  @IsOptional()
  @IsInt()
  @Min(1)
  @Max(5)
  quality?: number;

  @IsOptional()
  @IsInt()
  @Min(1)
  @Max(5)
  timeliness?: number;
}

class CreateReviewDto {
  @IsUUID()
  reviewerId: string;

  @IsUUID()
  targetId: string;

  @IsUUID()
  purchaseId: string;

  @IsEnum(ReviewRole)
  role: ReviewRole;

  @IsInt()
  @Min(1)
  @Max(5)
  rating: number;

  @IsOptional()
  @IsObject()
  @ValidateNested()
  @Type(() => CategoryRatingsDto)
  categories?: CategoryRatingsDto;

  @IsOptional()
  @IsString()
  comment?: string;

  @IsString()
  expiresAt: string;
}

@Controller()
export class ReviewsController {
  constructor(private readonly reviewsService: ReviewsService) {}

  @Post('reviews')
  @HttpCode(HttpStatus.CREATED)
  async createReview(@Body() dto: CreateReviewDto) {
    const review = await this.reviewsService.createReview({
      reviewerId: dto.reviewerId,
      targetId: dto.targetId,
      purchaseId: dto.purchaseId,
      role: dto.role,
      rating: dto.rating,
      categories: dto.categories,
      comment: dto.comment,
      expiresAt: new Date(dto.expiresAt),
    });
    return { success: true, data: review };
  }

  @Get('reviews/user/:userId')
  async getReviewsForUser(
    @Param('userId', ParseUUIDPipe) userId: string,
    @Query('role') role?: ReviewRole,
    @Query('limit') limit?: string,
    @Query('offset') offset?: string,
  ) {
    const result = await this.reviewsService.getReviewsForUser(userId, {
      role,
      limit: limit ? parseInt(limit, 10) : undefined,
      offset: offset ? parseInt(offset, 10) : undefined,
    });
    return { success: true, data: result };
  }

  @Get('reputation/:userId')
  async getReputation(@Param('userId', ParseUUIDPipe) userId: string) {
    const reputation = await this.reviewsService.getReputationScore(userId);
    const limits = this.reviewsService.getUserLimits(reputation);
    return {
      success: true,
      data: {
        ...reputation,
        limits,
      },
    };
  }

  /**
   * Returns the user's average rating broken down by role (buyer, organizer, supplier).
   * This lets the UI display separate star ratings for each context a user operates in.
   * GET /reputation/:userId/ratings-by-role
   */
  @Get('reputation/:userId/ratings-by-role')
  async getRatingsByRole(@Param('userId', ParseUUIDPipe) userId: string) {
    const ratings = await this.reviewsService.getRatingsByRole(userId);
    return { success: true, data: ratings };
  }

  @Get('health')
  health() {
    return { status: 'ok', service: 'reputation-service' };
  }
}

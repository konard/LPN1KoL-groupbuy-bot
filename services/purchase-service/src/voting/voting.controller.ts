import {
  Controller,
  Post,
  Get,
  Patch,
  Body,
  Param,
  Headers,
  HttpCode,
  HttpStatus,
  ParseUUIDPipe,
} from '@nestjs/common';
import {
  IsUUID,
  IsDateString,
  IsOptional,
  IsBoolean,
  IsNumber,
  IsString,
  IsUrl,
  Min,
} from 'class-validator';
import { VotingService } from './voting.service';

class CreateSessionDto {
  @IsUUID()
  purchaseId: string;

  @IsDateString()
  closesAt: string;

  @IsOptional()
  @IsBoolean()
  allowAddCandidates?: boolean;

  @IsOptional()
  @IsBoolean()
  allowChangeVote?: boolean;

  @IsOptional()
  @IsNumber()
  @Min(1)
  minVotesToClose?: number;

  @IsOptional()
  @IsNumber()
  @Min(1)
  votingDuration?: number;
}

class ResolveTieDto {
  @IsUUID()
  candidateId: string;
}

class AddCandidateDto {
  @IsString()
  supplierName: string;

  @IsOptional()
  @IsString()
  description?: string;

  @IsOptional()
  @IsNumber()
  pricePerUnit?: number;

  @IsOptional()
  @IsString()
  unit?: string;

  @IsOptional()
  @IsUrl()
  supplierUrl?: string;
}

class CastVoteDto {
  @IsUUID()
  candidateId: string;

  @IsOptional()
  @IsString()
  comment?: string;
}

function getUserId(headers: Record<string, string>): string {
  const userId = headers['x-user-id'];
  if (!userId) throw new Error('x-user-id header is required');
  return userId;
}

@Controller()
export class VotingController {
  constructor(private readonly votingService: VotingService) {}

  @Post('sessions')
  @HttpCode(HttpStatus.CREATED)
  async createSession(
    @Body() dto: CreateSessionDto,
    @Headers() headers: Record<string, string>,
  ) {
    const session = await this.votingService.createSession({
      purchaseId: dto.purchaseId,
      closesAt: new Date(dto.closesAt),
      allowAddCandidates: dto.allowAddCandidates,
      allowChangeVote: dto.allowChangeVote,
      minVotesToClose: dto.minVotesToClose,
      votingDuration: dto.votingDuration,
    });
    return { success: true, data: session };
  }

  @Post('sessions/:sessionId/candidates')
  @HttpCode(HttpStatus.CREATED)
  async addCandidate(
    @Param('sessionId', ParseUUIDPipe) sessionId: string,
    @Body() dto: AddCandidateDto,
    @Headers() headers: Record<string, string>,
  ) {
    const userId = getUserId(headers);
    const candidate = await this.votingService.addCandidate(sessionId, userId, dto);
    return { success: true, data: candidate };
  }

  @Post('sessions/:sessionId/votes')
  @HttpCode(HttpStatus.OK)
  async castVote(
    @Param('sessionId', ParseUUIDPipe) sessionId: string,
    @Body() dto: CastVoteDto,
    @Headers() headers: Record<string, string>,
  ) {
    const userId = getUserId(headers);
    const vote = await this.votingService.castVote(sessionId, userId, {
      candidateId: dto.candidateId,
      comment: dto.comment,
    });
    return { success: true, data: vote };
  }

  @Get('sessions/:sessionId/results')
  async getResults(
    @Param('sessionId', ParseUUIDPipe) sessionId: string,
    @Headers() headers: Record<string, string>,
  ) {
    // userId is optional — unauthenticated callers get voted: false on all options
    const userId = headers['x-user-id'] ?? null;
    const results = await this.votingService.getSessionResults(sessionId, userId);
    return { success: true, data: results };
  }

  @Patch('sessions/:sessionId/close')
  @HttpCode(HttpStatus.OK)
  async closeSession(
    @Param('sessionId', ParseUUIDPipe) sessionId: string,
    @Headers() headers: Record<string, string>,
  ) {
    const userId = getUserId(headers);
    const session = await this.votingService.closeSession(sessionId, userId);
    return { success: true, data: session };
  }

  @Post('sessions/:sessionId/resolve-tie')
  @HttpCode(HttpStatus.OK)
  async resolveTie(
    @Param('sessionId', ParseUUIDPipe) sessionId: string,
    @Body() dto: ResolveTieDto,
    @Headers() headers: Record<string, string>,
  ) {
    const userId = getUserId(headers);
    const session = await this.votingService.resolveTie(sessionId, dto.candidateId, userId);
    return { success: true, data: session };
  }
}

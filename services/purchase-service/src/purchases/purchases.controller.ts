import {
  Controller,
  Get,
  Post,
  Put,
  Delete,
  Body,
  Param,
  Query,
  Headers,
  HttpCode,
  HttpStatus,
  ParseUUIDPipe,
  ParseIntPipe,
  DefaultValuePipe,
} from '@nestjs/common';
import {
  IsString,
  IsOptional,
  IsNumber,
  IsDateString,
  IsUUID,
  MinLength,
  Min,
} from 'class-validator';
import { PurchasesService, CreatePurchaseDto as CreatePurchaseInput } from './purchases.service';

class AddEditorDto {
  @IsString()
  user_id: string;
}

class InviteParticipantDto {
  /** UUID of the user being invited to join the purchase. */
  @IsUUID()
  user_id: string;
}

class CreatePurchaseDto {
  @IsString()
  @MinLength(3)
  title: string;

  @IsOptional()
  @IsString()
  description?: string;

  @IsOptional()
  @IsNumber()
  @Min(2)
  minParticipants?: number;

  @IsOptional()
  @IsNumber()
  maxParticipants?: number;

  @IsOptional()
  @IsNumber()
  targetAmount?: number;

  @IsOptional()
  @IsString()
  currency?: string;

  @IsOptional()
  @IsString()
  category?: string;

  @IsOptional()
  @IsNumber()
  @Min(0)
  commissionPercent?: number;

  @IsOptional()
  @IsNumber()
  escrowThreshold?: number;

  @IsOptional()
  @IsDateString()
  deadlineAt?: string;
}

function getUserId(headers: Record<string, string>): string {
  const userId = headers['x-user-id'];
  if (!userId) throw new Error('x-user-id header required');
  return userId;
}

@Controller()
export class PurchasesController {
  constructor(private readonly purchasesService: PurchasesService) {}

  @Get('health')
  health() {
    return { status: 'ok', service: 'purchase-service' };
  }

  @Post()
  @HttpCode(HttpStatus.CREATED)
  async create(
    @Body() dto: CreatePurchaseDto,
    @Headers() headers: Record<string, string>,
  ) {
    const organizerId = getUserId(headers);
    const input: CreatePurchaseInput = {
      ...dto,
      organizerId,
      deadlineAt: dto.deadlineAt ? new Date(dto.deadlineAt) : undefined,
    };
    const purchase = await this.purchasesService.create(input);
    return { success: true, data: purchase };
  }

  @Get()
  async findAll(
    @Query('page', new DefaultValuePipe(1), ParseIntPipe) page: number,
    @Query('limit', new DefaultValuePipe(20), ParseIntPipe) limit: number,
  ) {
    const result = await this.purchasesService.findAll(page, Math.min(limit, 100));
    return { success: true, ...result };
  }

  @Get(':id')
  async findById(@Param('id', ParseUUIDPipe) id: string) {
    const purchase = await this.purchasesService.findById(id);
    return { success: true, data: purchase };
  }

  @Put(':id')
  async update(
    @Param('id', ParseUUIDPipe) id: string,
    @Body() dto: Partial<CreatePurchaseDto>,
    @Headers() headers: Record<string, string>,
  ) {
    const requesterId = getUserId(headers);
    const updates: Partial<CreatePurchaseInput> = {
      ...dto,
      deadlineAt: dto.deadlineAt ? new Date(dto.deadlineAt) : undefined,
    };
    const purchase = await this.purchasesService.update(id, requesterId, updates);
    return { success: true, data: purchase };
  }

  @Delete(':id')
  @HttpCode(HttpStatus.OK)
  async cancel(
    @Param('id', ParseUUIDPipe) id: string,
    @Headers() headers: Record<string, string>,
  ) {
    const requesterId = getUserId(headers);
    const purchase = await this.purchasesService.cancel(id, requesterId);
    return { success: true, data: purchase };
  }

  /** List all editors of a purchase. */
  @Get(':id/editors')
  async listEditors(@Param('id', ParseUUIDPipe) id: string) {
    const editors = await this.purchasesService.listEditors(id);
    return { success: true, data: editors };
  }

  /** Add an editor to a purchase (owner only). */
  @Post(':id/editors')
  @HttpCode(HttpStatus.CREATED)
  async addEditor(
    @Param('id', ParseUUIDPipe) id: string,
    @Body() dto: AddEditorDto,
    @Headers() headers: Record<string, string>,
  ) {
    const requesterId = getUserId(headers);
    const pu = await this.purchasesService.addEditor(id, requesterId, dto.user_id);
    return { success: true, data: pu };
  }

  /** Remove an editor from a purchase (owner only). */
  @Delete(':id/editors/:userId')
  @HttpCode(HttpStatus.OK)
  async removeEditor(
    @Param('id', ParseUUIDPipe) id: string,
    @Param('userId') userId: string,
    @Headers() headers: Record<string, string>,
  ) {
    const requesterId = getUserId(headers);
    await this.purchasesService.removeEditor(id, requesterId, userId);
    return { success: true };
  }

  /**
   * Invite a user to participate in a purchase.
   * Any existing participant or the organizer can invite another user.
   * The invited user will appear as a pending participant until they confirm.
   */
  @Post(':id/invite')
  @HttpCode(HttpStatus.OK)
  async inviteParticipant(
    @Param('id', ParseUUIDPipe) id: string,
    @Body() dto: InviteParticipantDto,
    @Headers() headers: Record<string, string>,
  ) {
    const requesterId = getUserId(headers);
    const result = await this.purchasesService.inviteParticipant(id, requesterId, dto.user_id);
    return { success: true, data: result };
  }
}

import {
  Controller,
  Post,
  Get,
  Patch,
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
  IsString,
  IsOptional,
  IsArray,
  MinLength,
} from 'class-validator';
import { ComplaintsService } from './complaints.service';
import { ComplaintType, ComplaintStatus } from './complaints.entity';

class FileComplaintDto {
  @IsUUID()
  reporterId: string;

  @IsUUID()
  targetId: string;

  @IsOptional()
  @IsUUID()
  purchaseId?: string;

  @IsEnum(ComplaintType)
  type: ComplaintType;

  @IsString()
  @MinLength(10)
  description: string;

  @IsOptional()
  @IsArray()
  @IsString({ each: true })
  evidenceUrls?: string[];
}

class ResolveComplaintDto {
  @IsUUID()
  adminId: string;

  @IsEnum(ComplaintStatus)
  status: ComplaintStatus.RESOLVED | ComplaintStatus.REJECTED;

  @IsString()
  @MinLength(5)
  resolution: string;
}

@Controller('complaints')
export class ComplaintsController {
  constructor(private readonly complaintsService: ComplaintsService) {}

  @Post()
  @HttpCode(HttpStatus.CREATED)
  async fileComplaint(@Body() dto: FileComplaintDto) {
    const complaint = await this.complaintsService.fileComplaint({
      reporterId: dto.reporterId,
      targetId: dto.targetId,
      purchaseId: dto.purchaseId,
      type: dto.type,
      description: dto.description,
      evidenceUrls: dto.evidenceUrls,
    });
    return { success: true, data: complaint };
  }

  @Get()
  async getComplaints(
    @Query('status') status?: ComplaintStatus,
    @Query('limit') limit?: string,
    @Query('offset') offset?: string,
  ) {
    const result = await this.complaintsService.getComplaints({
      status,
      limit: limit ? parseInt(limit, 10) : undefined,
      offset: offset ? parseInt(offset, 10) : undefined,
    });
    return { success: true, data: result };
  }

  @Get('user/:userId')
  async getComplaintsForUser(
    @Param('userId', ParseUUIDPipe) userId: string,
    @Query('limit') limit?: string,
    @Query('offset') offset?: string,
  ) {
    const result = await this.complaintsService.getComplaintsForUser(userId, {
      limit: limit ? parseInt(limit, 10) : undefined,
      offset: offset ? parseInt(offset, 10) : undefined,
    });
    return { success: true, data: result };
  }

  @Patch(':id/resolve')
  async resolveComplaint(
    @Param('id', ParseUUIDPipe) id: string,
    @Body() dto: ResolveComplaintDto,
  ) {
    const complaint = await this.complaintsService.resolveComplaint(id, {
      adminId: dto.adminId,
      status: dto.status,
      resolution: dto.resolution,
    });
    return { success: true, data: complaint };
  }
}

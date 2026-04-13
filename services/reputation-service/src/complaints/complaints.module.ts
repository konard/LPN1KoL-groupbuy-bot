import { Module } from '@nestjs/common';
import { TypeOrmModule } from '@nestjs/typeorm';
import { Complaint } from './complaints.entity';
import { ComplaintsService } from './complaints.service';
import { ComplaintsController } from './complaints.controller';

@Module({
  imports: [TypeOrmModule.forFeature([Complaint])],
  controllers: [ComplaintsController],
  providers: [ComplaintsService],
  exports: [ComplaintsService],
})
export class ComplaintsModule {}

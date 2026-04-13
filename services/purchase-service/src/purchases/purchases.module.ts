import { Module } from '@nestjs/common';
import { TypeOrmModule } from '@nestjs/typeorm';
import { Purchase } from './purchases.entity';
import { PurchaseUser } from './purchase-user.entity';
import { PurchasesController } from './purchases.controller';
import { PurchasesService } from './purchases.service';
import { KafkaModule } from '../kafka/kafka.module';

@Module({
  imports: [TypeOrmModule.forFeature([Purchase, PurchaseUser]), KafkaModule],
  controllers: [PurchasesController],
  providers: [PurchasesService],
  exports: [PurchasesService],
})
export class PurchasesModule {}

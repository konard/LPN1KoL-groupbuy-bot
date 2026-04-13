import { Module } from '@nestjs/common';
import { ConfigModule, ConfigService } from '@nestjs/config';
import { TypeOrmModule } from '@nestjs/typeorm';
import { ScheduleModule } from '@nestjs/schedule';
import { PurchasesModule } from './purchases/purchases.module';
import { VotingModule } from './voting/voting.module';
import { KafkaModule } from './kafka/kafka.module';
import { Purchase } from './purchases/purchases.entity';
import { PurchaseUser } from './purchases/purchase-user.entity';
import { VotingSession, Vote, Candidate } from './voting/voting.entity';

@Module({
  imports: [
    ConfigModule.forRoot({ isGlobal: true }),
    ScheduleModule.forRoot(),
    TypeOrmModule.forRootAsync({
      imports: [ConfigModule],
      inject: [ConfigService],
      useFactory: (config: ConfigService) => ({
        type: 'postgres',
        url: config.get<string>('DATABASE_URL'),
        entities: [Purchase, PurchaseUser, VotingSession, Vote, Candidate],
        synchronize: false,
      }),
    }),
    KafkaModule,
    PurchasesModule,
    VotingModule,
  ],
})
export class AppModule {}

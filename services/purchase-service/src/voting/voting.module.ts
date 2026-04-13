import { Module } from '@nestjs/common';
import { TypeOrmModule } from '@nestjs/typeorm';
import { VotingSession, Candidate, Vote } from './voting.entity';
import { VotingController } from './voting.controller';
import { VotingService } from './voting.service';
import { Purchase } from '../purchases/purchases.entity';
import { KafkaModule } from '../kafka/kafka.module';

@Module({
  imports: [
    TypeOrmModule.forFeature([VotingSession, Candidate, Vote, Purchase]),
    KafkaModule,
  ],
  controllers: [VotingController],
  providers: [VotingService],
  exports: [VotingService],
})
export class VotingModule {}

import { Module } from '@nestjs/common';
import { ConfigModule } from '@nestjs/config';
import { KafkaConsumer } from './kafka.consumer';
import { ReviewsModule } from '../reviews/reviews.module';

@Module({
  imports: [ConfigModule, ReviewsModule],
  providers: [KafkaConsumer],
  exports: [KafkaConsumer],
})
export class KafkaModule {}

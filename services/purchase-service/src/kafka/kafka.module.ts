import { Module, Global } from '@nestjs/common';
import { ConfigModule, ConfigService } from '@nestjs/config';
import { KafkaProducer } from './kafka.producer';

@Global()
@Module({
  imports: [ConfigModule],
  providers: [KafkaProducer],
  exports: [KafkaProducer],
})
export class KafkaModule {}

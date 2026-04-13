import { Module } from '@nestjs/common';
import { ConfigModule, ConfigService } from '@nestjs/config';
import { TypeOrmModule } from '@nestjs/typeorm';
import { ReviewsModule } from './reviews/reviews.module';
import { ComplaintsModule } from './complaints/complaints.module';
import { KafkaModule } from './kafka/kafka.module';
import { Review } from './reviews/reviews.entity';
import { Complaint } from './complaints/complaints.entity';

@Module({
  imports: [
    ConfigModule.forRoot({ isGlobal: true }),
    TypeOrmModule.forRootAsync({
      imports: [ConfigModule],
      inject: [ConfigService],
      useFactory: (config: ConfigService) => ({
        type: 'postgres',
        url: config.get<string>(
          'DATABASE_URL',
          'postgresql://reputation_user:reputation_password@localhost:5432/reputation_db',
        ),
        entities: [Review, Complaint],
        synchronize: config.get('NODE_ENV') !== 'production',
        ssl: config.get('DB_SSL') === 'true' ? { rejectUnauthorized: false } : false,
      }),
    }),
    ReviewsModule,
    ComplaintsModule,
    KafkaModule,
  ],
})
export class AppModule {}

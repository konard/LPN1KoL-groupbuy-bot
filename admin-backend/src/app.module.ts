import { Module } from '@nestjs/common';
import { TypeOrmModule } from '@nestjs/typeorm';
import { HealthController } from './health/health.controller';
import { AuthController } from './auth/auth.controller';
import { UsersController } from './users/users.controller';
import { ProcurementsController } from './procurements/procurements.controller';
import { PaymentsController } from './payments/payments.controller';
import { DashboardController } from './dashboard/dashboard.controller';

@Module({
  imports: [
    TypeOrmModule.forRoot({
      type: 'postgres',
      url: process.env.DATABASE_URL,
      entities: [],
      synchronize: false,
    }),
  ],
  controllers: [
    HealthController,
    AuthController,
    UsersController,
    ProcurementsController,
    PaymentsController,
    DashboardController,
  ],
})
export class AppModule {}

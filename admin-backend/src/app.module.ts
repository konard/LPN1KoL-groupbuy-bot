import { Module } from '@nestjs/common';
import { TypeOrmModule } from '@nestjs/typeorm';

@Module({
  imports: [
    TypeOrmModule.forRoot({
      type: 'postgres',
      url: process.env.DATABASE_URL,
      entities: [],
      // Read-only: no synchronize, no migrations run from admin-backend
      synchronize: false,
    }),
  ],
})
export class AppModule {}

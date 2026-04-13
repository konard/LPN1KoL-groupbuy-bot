import { Module } from '@nestjs/common';
import { ConfigModule, ConfigService } from '@nestjs/config';
import { TypeOrmModule } from '@nestjs/typeorm';
import { AuthModule } from './auth/auth.module';
import { UsersModule } from './users/users.module';
import { User } from './users/users.entity';
import { AuditBan } from './users/audit-ban.entity';
import { CreateUsers1000000000001 } from './migrations/001_create_users';
import { AddPhoneColumn1000000000004 } from './migrations/004_add_phone_column';
import { DropPasswordHash1000000000005 } from './migrations/005_drop_password_hash';
import { BanSystem1000000000006 } from './migrations/006_ban_system';

@Module({
  imports: [
    ConfigModule.forRoot({ isGlobal: true }),
    TypeOrmModule.forRootAsync({
      imports: [ConfigModule],
      inject: [ConfigService],
      useFactory: (config: ConfigService) => ({
        type: 'postgres',
        url: config.get<string>('DATABASE_URL'),
        entities: [User, AuditBan],
        synchronize: false,
        migrationsRun: true,
        migrations: [
          CreateUsers1000000000001,
          AddPhoneColumn1000000000004,
          DropPasswordHash1000000000005,
          BanSystem1000000000006,
        ],
        ssl: config.get('DB_SSL') === 'true' ? { rejectUnauthorized: false } : false,
      }),
    }),
    UsersModule,
    AuthModule,
  ],
})
export class AppModule {}

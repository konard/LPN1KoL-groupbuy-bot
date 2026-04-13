import { DataSource } from 'typeorm';
import { User } from './users/users.entity';
import { AuditBan } from './users/audit-ban.entity';
import { CreateUsers1000000000001 } from './migrations/001_create_users';
import { AddPhoneColumn1000000000004 } from './migrations/004_add_phone_column';
import { DropPasswordHash1000000000005 } from './migrations/005_drop_password_hash';
import { BanSystem1000000000006 } from './migrations/006_ban_system';

export default new DataSource({
  type: 'postgres',
  url: process.env.DATABASE_URL,
  entities: [User, AuditBan],
  migrations: [
    CreateUsers1000000000001,
    AddPhoneColumn1000000000004,
    DropPasswordHash1000000000005,
    BanSystem1000000000006,
  ],
  synchronize: false,
});

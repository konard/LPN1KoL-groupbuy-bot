import { Controller, Get, UseGuards } from '@nestjs/common';
import { InjectDataSource } from '@nestjs/typeorm';
import { DataSource } from 'typeorm';
import { AdminAuthGuard } from '../auth/auth.guard';

@Controller('dashboard')
@UseGuards(AdminAuthGuard)
export class DashboardController {
  constructor(@InjectDataSource() private readonly db: DataSource) {}

  @Get()
  async stats() {
    const [[{ count: users }], [{ count: purchases }], [{ count: payments }]] = await Promise.all([
      this.db.query(`SELECT COUNT(*) FROM auth.users`),
      this.db.query(`SELECT COUNT(*) FROM purchase.purchases`),
      this.db.query(`SELECT COUNT(*) FROM payment.wallets`),
    ]);
    return {
      users: parseInt(users),
      purchases: parseInt(purchases),
      payments: parseInt(payments),
    };
  }
}

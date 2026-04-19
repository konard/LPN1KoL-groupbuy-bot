import { Controller, Get, Param, Query, UseGuards } from '@nestjs/common';
import { InjectDataSource } from '@nestjs/typeorm';
import { DataSource } from 'typeorm';
import { AdminAuthGuard } from '../auth/auth.guard';

@Controller('payments')
@UseGuards(AdminAuthGuard)
export class PaymentsController {
  constructor(@InjectDataSource() private readonly db: DataSource) {}

  @Get()
  async list(@Query('page') page = '1', @Query('limit') limit = '50') {
    const offset = (parseInt(page) - 1) * parseInt(limit);
    const rows = await this.db.query(
      `SELECT * FROM payment.wallets ORDER BY created_at DESC LIMIT ${parseInt(limit)} OFFSET ${offset}`
    );
    const [{ count }] = await this.db.query(`SELECT COUNT(*) FROM payment.wallets`);
    return { results: rows, count: parseInt(count) };
  }

  @Get('summary')
  async summary() {
    const [{ total_balance }] = await this.db.query(
      `SELECT COALESCE(SUM(balance), 0) AS total_balance FROM payment.wallets`
    );
    const [{ count }] = await this.db.query(`SELECT COUNT(*) FROM payment.wallets`);
    return { total_balance, wallet_count: parseInt(count) };
  }

  @Get(':id')
  async get(@Param('id') id: string) {
    const [row] = await this.db.query(`SELECT * FROM payment.wallets WHERE id = $1`, [id]);
    return row;
  }
}

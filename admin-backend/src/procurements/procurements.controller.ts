import { Controller, Get, Patch, Delete, Post, Body, Param, Query, UseGuards } from '@nestjs/common';
import { InjectDataSource } from '@nestjs/typeorm';
import { DataSource } from 'typeorm';
import { AdminAuthGuard } from '../auth/auth.guard';

@Controller('procurements')
@UseGuards(AdminAuthGuard)
export class ProcurementsController {
  constructor(@InjectDataSource() private readonly db: DataSource) {}

  @Get()
  async list(@Query('search') search?: string, @Query('page') page = '1', @Query('limit') limit = '50') {
    const offset = (parseInt(page) - 1) * parseInt(limit);
    let query = `SELECT * FROM purchase.purchases`;
    const params: any[] = [];
    if (search) {
      params.push(`%${search}%`);
      query += ` WHERE title ILIKE $1`;
    }
    query += ` ORDER BY created_at DESC LIMIT ${parseInt(limit)} OFFSET ${offset}`;
    const rows = await this.db.query(query, params);
    const [{ count }] = await this.db.query(`SELECT COUNT(*) FROM purchase.purchases`);
    return { results: rows, count: parseInt(count) };
  }

  @Get(':id')
  async get(@Param('id') id: string) {
    const [row] = await this.db.query(`SELECT * FROM purchase.purchases WHERE id = $1`, [id]);
    return row;
  }

  @Patch(':id')
  async update(@Param('id') id: string, @Body() body: any) {
    const allowed = ['title', 'status', 'description'];
    const sets = Object.keys(body).filter(k => allowed.includes(k));
    if (!sets.length) return { detail: 'No valid fields' };
    const params = sets.map((k, i) => `${k} = $${i + 1}`).join(', ');
    const values = sets.map(k => body[k]);
    values.push(id);
    await this.db.query(`UPDATE purchase.purchases SET ${params} WHERE id = $${values.length}`, values);
    return this.get(id);
  }

  @Delete(':id')
  async remove(@Param('id') id: string) {
    await this.db.query(`DELETE FROM purchase.purchases WHERE id = $1`, [id]);
    return { detail: 'Deleted' };
  }

  @Post(':id/update_status')
  async updateStatus(@Param('id') id: string, @Body() body: { status: string }) {
    await this.db.query(`UPDATE purchase.purchases SET status = $1 WHERE id = $2`, [body.status, id]);
    return this.get(id);
  }
}

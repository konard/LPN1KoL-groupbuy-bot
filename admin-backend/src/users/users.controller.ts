import { Controller, Get, Patch, Delete, Post, Body, Param, Query, UseGuards } from '@nestjs/common';
import { InjectDataSource } from '@nestjs/typeorm';
import { DataSource } from 'typeorm';
import { AdminAuthGuard } from '../auth/auth.guard';

@Controller('users')
@UseGuards(AdminAuthGuard)
export class UsersController {
  constructor(@InjectDataSource() private readonly db: DataSource) {}

  @Get()
  async list(@Query('search') search?: string, @Query('page') page = '1', @Query('limit') limit = '50') {
    const offset = (parseInt(page) - 1) * parseInt(limit);
    let query = `SELECT id, email, is_active, totp_enabled, created_at FROM auth.users`;
    const params: any[] = [];
    if (search) {
      params.push(`%${search}%`);
      query += ` WHERE email ILIKE $1`;
    }
    query += ` ORDER BY created_at DESC LIMIT ${parseInt(limit)} OFFSET ${offset}`;
    const rows = await this.db.query(query, params);
    const [{ count }] = await this.db.query(`SELECT COUNT(*) FROM auth.users`);
    return { results: rows, count: parseInt(count) };
  }

  @Get(':id')
  async get(@Param('id') id: string) {
    const [row] = await this.db.query(
      `SELECT id, email, is_active, totp_enabled, created_at FROM auth.users WHERE id = $1`,
      [id]
    );
    return row;
  }

  @Patch(':id')
  async update(@Param('id') id: string, @Body() body: any) {
    const allowed = ['is_active'];
    const sets = Object.keys(body).filter(k => allowed.includes(k));
    if (!sets.length) return { detail: 'No valid fields' };
    const params = sets.map((k, i) => `${k} = $${i + 1}`).join(', ');
    const values = sets.map(k => body[k]);
    values.push(id);
    await this.db.query(`UPDATE auth.users SET ${params} WHERE id = $${values.length}`, values);
    return this.get(id);
  }

  @Delete(':id')
  async remove(@Param('id') id: string) {
    await this.db.query(`DELETE FROM auth.users WHERE id = $1`, [id]);
    return { detail: 'Deleted' };
  }

  @Post(':id/toggle_active')
  async toggleActive(@Param('id') id: string) {
    await this.db.query(`UPDATE auth.users SET is_active = NOT is_active WHERE id = $1`, [id]);
    return this.get(id);
  }
}

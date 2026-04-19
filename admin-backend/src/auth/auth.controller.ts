import { Controller, Post, Get, Delete, Body, Req, Res, UnauthorizedException } from '@nestjs/common';
import { Request, Response } from 'express';
import * as jwt from 'jsonwebtoken';

const ADMIN_USERNAME = process.env.ADMIN_USERNAME || 'admin';
const ADMIN_PASSWORD = process.env.ADMIN_PASSWORD || 'admin';
const JWT_SECRET = process.env.JWT_SECRET || 'change_me_in_production';

@Controller('auth')
export class AuthController {
  @Post('login')
  login(@Body() body: { username: string; password: string }, @Res() res: Response) {
    if (body.username !== ADMIN_USERNAME || body.password !== ADMIN_PASSWORD) {
      throw new UnauthorizedException('Invalid credentials');
    }
    const token = jwt.sign({ sub: body.username, role: 'admin' }, JWT_SECRET, { expiresIn: '8h' });
    res.cookie('admin_token', token, { httpOnly: true, sameSite: 'lax' });
    return res.json({ token });
  }

  @Get()
  checkAuth(@Req() req: Request) {
    const token = req.cookies?.admin_token || req.headers.authorization?.replace('Bearer ', '');
    if (!token) throw new UnauthorizedException();
    try {
      const payload = jwt.verify(token, JWT_SECRET);
      return { authenticated: true, user: payload };
    } catch {
      throw new UnauthorizedException();
    }
  }

  @Delete()
  logout(@Res() res: Response) {
    res.clearCookie('admin_token');
    return res.json({ detail: 'Logged out' });
  }
}

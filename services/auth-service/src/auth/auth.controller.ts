import {
  Controller,
  Post,
  Body,
  HttpCode,
  HttpStatus,
  Headers,
  UnauthorizedException,
  Get,
  Req,
} from '@nestjs/common';
import {
  IsEmail,
  IsString,
  IsOptional,
  IsEnum,
  IsIn,
  Matches,
  Length,
} from 'class-validator';
import { AuthService } from './auth.service';
import { UserRole } from '../users/users.entity';

// ─── DTOs ──────────────────────────────────────────────────────────────────────

class RegisterDto {
  @IsString()
  @Matches(/^\+?[1-9]\d{6,19}$/, { message: 'Invalid phone number format' })
  phone: string;

  @IsEmail()
  email: string;

  @IsString()
  @IsOptional()
  firstName?: string;

  @IsString()
  @IsOptional()
  lastName?: string;

  @IsEnum(UserRole)
  @IsOptional()
  role?: UserRole;
}

class ConfirmRegistrationDto {
  @IsString()
  @Matches(/^\+?[1-9]\d{6,19}$/, { message: 'Invalid phone number format' })
  phone: string;

  @IsString()
  @Length(4, 8)
  otp: string;
}

class LoginDto {
  @IsString()
  @Matches(/^\+?[1-9]\d{6,19}$/, { message: 'Invalid phone number format' })
  phone: string;
}

class ConfirmLoginDto {
  @IsString()
  @Matches(/^\+?[1-9]\d{6,19}$/, { message: 'Invalid phone number format' })
  phone: string;

  @IsString()
  @Length(4, 8)
  otp: string;
}

class ResendOtpDto {
  @IsString()
  @Matches(/^\+?[1-9]\d{6,19}$/, { message: 'Invalid phone number format' })
  phone: string;

  @IsString()
  @IsIn(['login', 'registration'])
  context: 'login' | 'registration';
}

class RefreshDto {
  @IsString()
  refreshToken: string;
}

class TwoFactorVerifyDto {
  @IsString()
  code: string;
}

class TwoFactorLoginDto {
  @IsString()
  tempToken: string;

  @IsString()
  code: string;
}

class TwoFactorDisableDto {
  @IsString()
  code: string;
}

class TwoFactorBackupCodesDto {
  @IsString()
  code: string;
}

// ─── Controller ────────────────────────────────────────────────────────────────

@Controller()
export class AuthController {
  constructor(private readonly authService: AuthService) {}

  /**
   * Step 1: Start registration — validates phone+email uniqueness, sends OTP to email.
   */
  @Post('register')
  @HttpCode(HttpStatus.OK)
  async register(@Body() dto: RegisterDto) {
    const result = await this.authService.registerWithPhone(
      dto.phone,
      dto.email,
      dto.firstName,
      dto.lastName,
      dto.role,
    );
    return { success: true, data: result };
  }

  /**
   * Step 2: Confirm registration — verify OTP and receive JWT tokens.
   */
  @Post('register/confirm')
  @HttpCode(HttpStatus.CREATED)
  async confirmRegistration(@Body() dto: ConfirmRegistrationDto) {
    const tokens = await this.authService.confirmRegistration(dto.phone, dto.otp);
    return { success: true, data: tokens };
  }

  /**
   * Step 1: Start login by phone — sends OTP to the user's registered email.
   */
  @Post('login')
  @HttpCode(HttpStatus.OK)
  async login(@Body() dto: LoginDto) {
    const result = await this.authService.loginWithPhone(dto.phone);
    return { success: true, data: result };
  }

  /**
   * Resend OTP code for an ongoing login or registration session.
   * Limited to once every 30 seconds per phone number.
   */
  @Post('resend-code')
  @HttpCode(HttpStatus.OK)
  async resendCode(@Body() dto: ResendOtpDto) {
    const result = await this.authService.resendOtp(dto.phone, dto.context);
    return { success: true, data: result };
  }

  /**
   * Step 2: Confirm login — verify OTP and receive JWT tokens (or 2FA temp token).
   */
  @Post('login/confirm')
  @HttpCode(HttpStatus.OK)
  async confirmLogin(@Body() dto: ConfirmLoginDto) {
    const result = await this.authService.confirmLogin(dto.phone, dto.otp);
    return { success: true, data: result };
  }

  @Post('refresh')
  @HttpCode(HttpStatus.OK)
  async refresh(@Body() dto: RefreshDto) {
    const tokens = await this.authService.refresh(dto.refreshToken);
    return { success: true, data: tokens };
  }

  @Post('logout')
  @HttpCode(HttpStatus.OK)
  async logout(@Headers('authorization') authHeader: string, @Req() req: any) {
    if (!authHeader?.startsWith('Bearer ')) {
      throw new UnauthorizedException('No token provided');
    }
    const token = authHeader.slice(7);
    const payload = await this.authService.validateToken(token);
    await this.authService.logout(token, payload.sub);
    return { success: true, message: 'Logged out successfully' };
  }

  @Get('validate')
  @HttpCode(HttpStatus.OK)
  async validate(@Headers('authorization') authHeader: string) {
    if (!authHeader?.startsWith('Bearer ')) {
      throw new UnauthorizedException('No token provided');
    }
    const token = authHeader.slice(7);
    const payload = await this.authService.validateToken(token);
    return { success: true, data: payload };
  }

  @Get('health')
  health() {
    return { status: 'ok', service: 'auth-service' };
  }

  // --- Two-Factor Authentication Endpoints ---

  @Post('2fa/enable')
  @HttpCode(HttpStatus.OK)
  async enable2FA(@Headers('authorization') authHeader: string) {
    const payload = await this.extractAndValidateToken(authHeader);
    const result = await this.authService.enable2FA(payload.sub);
    return { success: true, data: result };
  }

  @Post('2fa/verify')
  @HttpCode(HttpStatus.OK)
  async verify2FA(
    @Headers('authorization') authHeader: string,
    @Body() dto: TwoFactorVerifyDto,
  ) {
    const payload = await this.extractAndValidateToken(authHeader);
    await this.authService.verify2FA(payload.sub, dto.code);
    return { success: true, message: 'Two-factor authentication enabled successfully' };
  }

  @Post('2fa/login')
  @HttpCode(HttpStatus.OK)
  async login2FA(@Body() dto: TwoFactorLoginDto) {
    const tokens = await this.authService.loginWith2FA(dto.tempToken, dto.code);
    return { success: true, data: tokens };
  }

  @Post('2fa/disable')
  @HttpCode(HttpStatus.OK)
  async disable2FA(
    @Headers('authorization') authHeader: string,
    @Body() dto: TwoFactorDisableDto,
  ) {
    const payload = await this.extractAndValidateToken(authHeader);
    await this.authService.disable2FA(payload.sub, dto.code);
    return { success: true, message: 'Two-factor authentication disabled successfully' };
  }

  @Post('2fa/backup-codes')
  @HttpCode(HttpStatus.OK)
  async regenerateBackupCodes(
    @Headers('authorization') authHeader: string,
    @Body() dto: TwoFactorBackupCodesDto,
  ) {
    const payload = await this.extractAndValidateToken(authHeader);
    const backupCodes = await this.authService.regenerateBackupCodes(payload.sub, dto.code);
    return { success: true, data: { backupCodes } };
  }

  // --- Private helpers ---

  private async extractAndValidateToken(authHeader: string) {
    if (!authHeader?.startsWith('Bearer ')) {
      throw new UnauthorizedException('No token provided');
    }
    const token = authHeader.slice(7);
    return this.authService.validateToken(token);
  }
}

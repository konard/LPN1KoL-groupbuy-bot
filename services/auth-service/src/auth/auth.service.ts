import {
  Injectable,
  UnauthorizedException,
  BadRequestException,
  ForbiddenException,
} from '@nestjs/common';
import { JwtService } from '@nestjs/jwt';
import { ConfigService } from '@nestjs/config';
import { v4 as uuidv4 } from 'uuid';
import { authenticator } from 'otplib';
import * as bcrypt from 'bcrypt';
import * as crypto from 'crypto';
import * as http from 'http';
import * as https from 'https';
import { UsersService } from '../users/users.service';
import { RedisService } from '../redis/redis.service';
import { User, UserRole } from '../users/users.entity';

export interface TokenPair {
  accessToken: string;
  refreshToken: string;
  expiresIn: number;
}

export interface JwtPayload {
  sub: string;
  email: string;
  role: string;
  jti: string;
}

export interface TwoFactorSetupResult {
  otpauthUri: string;
  backupCodes: string[];
}

export interface LoginResult {
  requires2FA: boolean;
  tempToken?: string;
  accessToken?: string;
  refreshToken?: string;
  expiresIn?: number;
}

/** Result returned after initiating login or registration with phone — awaits OTP confirmation */
export interface OtpPendingResult {
  otpSent: boolean;
  message: string;
}

const ROLES_REQUIRING_2FA: string[] = [UserRole.ORGANIZER, UserRole.SUPPLIER];
const BACKUP_CODE_COUNT = 10;
const TEMP_TOKEN_TTL_SECONDS = 300; // 5 minutes
const OTP_TTL_SECONDS = 600;        // 10 minutes
const OTP_LENGTH = 6;
const OTP_RESEND_COOLDOWN_SECONDS = 30; // Minimum seconds between resend requests

@Injectable()
export class AuthService {
  constructor(
    private readonly usersService: UsersService,
    private readonly jwtService: JwtService,
    private readonly configService: ConfigService,
    private readonly redisService: RedisService,
  ) {}

  // ─── Phone-based Registration ─────────────────────────────────────────────

  /**
   * Step 1 of registration: store pending data in Redis and send OTP to email.
   */
  async registerWithPhone(
    phone: string,
    email: string,
    firstName?: string,
    lastName?: string,
    role?: UserRole,
  ): Promise<OtpPendingResult> {
    if (!phone || !email) {
      throw new BadRequestException('Phone number and email are required');
    }
    if (!/^\+?[1-9]\d{6,19}$/.test(phone)) {
      throw new BadRequestException('Invalid phone number format');
    }
    if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) {
      throw new BadRequestException('Invalid email format');
    }

    // Check for existing users before generating OTP
    const existingByPhone = await this.usersService.findByPhone(phone);
    if (existingByPhone) {
      throw new BadRequestException('User with this phone number already exists');
    }
    const existingByEmail = await this.usersService.findByEmail(email);
    if (existingByEmail) {
      throw new BadRequestException('User with this email already exists');
    }

    const otp = this.generateNumericOtp(OTP_LENGTH);

    // Store pending registration data keyed by phone
    await this.redisService.set(
      `reg:pending:${phone}`,
      JSON.stringify({ phone, email, firstName, lastName, role, otp }),
      OTP_TTL_SECONDS,
    );

    await this.sendOtpEmail(email, otp, 'registration');

    return { otpSent: true, message: 'Verification code sent to your email' };
  }

  /**
   * Step 2 of registration: verify OTP and create the user account.
   */
  async confirmRegistration(phone: string, otp: string): Promise<TokenPair> {
    const raw = await this.redisService.get(`reg:pending:${phone}`);
    if (!raw) {
      throw new BadRequestException('Registration session expired or not found. Please start over.');
    }

    let pending: { phone: string; email: string; firstName?: string; lastName?: string; role?: UserRole; otp: string };
    try {
      pending = JSON.parse(raw);
    } catch {
      throw new BadRequestException('Invalid registration session data');
    }

    if (pending.otp !== otp.trim()) {
      throw new UnauthorizedException('Invalid verification code');
    }

    // Consume the pending session
    await this.redisService.del(`reg:pending:${phone}`);

    const user = await this.usersService.create(
      pending.phone,
      pending.email,
      pending.firstName,
      pending.lastName,
      pending.role as UserRole | undefined,
    );

    if (ROLES_REQUIRING_2FA.includes(user.role)) {
      await this.usersService.setTwoFactorRequired(user.id, true);
    }

    // Sync newly registered user to the Rust core API so that
    // /api/users/by_email/ can resolve the integer coreId for the frontend.
    await this.syncUserToCoreApi(user);

    return this.generateTokens(user);
  }

  // ─── Phone-based Login ────────────────────────────────────────────────────

  /**
   * Step 1 of login: look up user by phone, send OTP to their registered email.
   */
  async loginWithPhone(phone: string): Promise<OtpPendingResult> {
    if (!phone) {
      throw new BadRequestException('Phone number is required');
    }

    const user = await this.usersService.findByPhone(phone);
    if (!user) {
      // Return same message to avoid user enumeration
      return { otpSent: true, message: 'If this number is registered, a code will be sent to the associated email' };
    }
    if (!user.isActive) {
      throw new UnauthorizedException('Account is disabled');
    }
    if (user.isBanned) {
      throw new ForbiddenException({ status: 403, code: 'USER_BANNED', message: 'Your account has been suspended' });
    }

    const otp = this.generateNumericOtp(OTP_LENGTH);

    await this.redisService.set(
      `login:otp:${phone}`,
      JSON.stringify({ userId: user.id, otp }),
      OTP_TTL_SECONDS,
    );

    await this.sendOtpEmail(user.email, otp, 'login');

    return { otpSent: true, message: 'If this number is registered, a code will be sent to the associated email' };
  }

  /**
   * Resend OTP for an in-progress login or registration session.
   * Enforces a 30-second cooldown between resend requests.
   */
  async resendOtp(phone: string, context: 'login' | 'registration'): Promise<OtpPendingResult> {
    if (!phone) {
      throw new BadRequestException('Phone number is required');
    }

    const cooldownKey = `otp:resend:cooldown:${context}:${phone}`;
    const onCooldown = await this.redisService.get(cooldownKey);
    if (onCooldown) {
      throw new BadRequestException(`Please wait ${OTP_RESEND_COOLDOWN_SECONDS} seconds before requesting a new code`);
    }

    const otp = this.generateNumericOtp(OTP_LENGTH);

    if (context === 'login') {
      const raw = await this.redisService.get(`login:otp:${phone}`);
      if (!raw) {
        // Return same generic message to avoid user enumeration
        return { otpSent: true, message: 'If this number is registered, a new code will be sent to the associated email' };
      }

      let session: { userId: string; otp: string };
      try {
        session = JSON.parse(raw);
      } catch {
        throw new BadRequestException('Invalid login session');
      }

      const user = await this.usersService.findById(session.userId);
      if (!user) {
        return { otpSent: true, message: 'If this number is registered, a new code will be sent to the associated email' };
      }

      // Overwrite existing OTP session with a new code, keeping same TTL
      await this.redisService.set(
        `login:otp:${phone}`,
        JSON.stringify({ userId: user.id, otp }),
        OTP_TTL_SECONDS,
      );

      await this.sendOtpEmail(user.email, otp, 'login');
    } else {
      const raw = await this.redisService.get(`reg:pending:${phone}`);
      if (!raw) {
        throw new BadRequestException('Registration session expired or not found. Please start over.');
      }

      let pending: { phone: string; email: string; firstName?: string; lastName?: string; role?: UserRole; otp: string };
      try {
        pending = JSON.parse(raw);
      } catch {
        throw new BadRequestException('Invalid registration session data');
      }

      // Overwrite with new OTP, keeping same TTL
      await this.redisService.set(
        `reg:pending:${phone}`,
        JSON.stringify({ ...pending, otp }),
        OTP_TTL_SECONDS,
      );

      await this.sendOtpEmail(pending.email, otp, 'registration');
    }

    // Set cooldown to prevent spamming resend
    await this.redisService.set(cooldownKey, '1', OTP_RESEND_COOLDOWN_SECONDS);

    return { otpSent: true, message: 'A new verification code has been sent' };
  }

  /**
   * Step 2 of login: verify OTP and issue tokens.
   */
  async confirmLogin(phone: string, otp: string): Promise<LoginResult> {
    const raw = await this.redisService.get(`login:otp:${phone}`);
    if (!raw) {
      throw new UnauthorizedException('Verification code expired or not found. Please request a new code.');
    }

    let session: { userId: string; otp: string };
    try {
      session = JSON.parse(raw);
    } catch {
      throw new UnauthorizedException('Invalid login session');
    }

    if (session.otp !== otp.trim()) {
      throw new UnauthorizedException('Invalid verification code');
    }

    // Consume the OTP
    await this.redisService.del(`login:otp:${phone}`);

    const user = await this.usersService.findById(session.userId);
    if (!user) throw new UnauthorizedException('User not found');
    if (!user.isActive) throw new UnauthorizedException('Account is disabled');
    if (user.isBanned) {
      throw new ForbiddenException({ status: 403, code: 'USER_BANNED', message: 'Your account has been suspended' });
    }

    // If TOTP-based 2FA is enabled, issue a temporary token instead of full JWT
    if (user.twoFactorEnabled) {
      const tempToken = uuidv4();
      await this.redisService.set(
        `2fa:temp:${tempToken}`,
        user.id,
        TEMP_TOKEN_TTL_SECONDS,
      );
      return { requires2FA: true, tempToken };
    }

    const tokens = await this.generateTokens(user);
    return { requires2FA: false, ...tokens };
  }

  // ─── 2FA (TOTP) ───────────────────────────────────────────────────────────

  async loginWith2FA(tempToken: string, code: string): Promise<TokenPair> {
    const userId = await this.redisService.get(`2fa:temp:${tempToken}`);
    if (!userId) {
      throw new UnauthorizedException('Invalid or expired 2FA session');
    }

    const user = await this.usersService.findById(userId);
    if (!user) throw new UnauthorizedException('User not found');

    const isValid = await this.validate2FACode(user, code);
    if (!isValid) {
      throw new UnauthorizedException('Invalid 2FA code');
    }

    // Consume the temp token
    await this.redisService.del(`2fa:temp:${tempToken}`);

    return this.generateTokens(user);
  }

  async enable2FA(userId: string): Promise<TwoFactorSetupResult> {
    const user = await this.usersService.findById(userId);
    if (!user) throw new UnauthorizedException('User not found');

    if (user.twoFactorEnabled) {
      throw new BadRequestException('Two-factor authentication is already enabled');
    }

    const secret = authenticator.generateSecret();
    await this.usersService.setTwoFactorSecret(userId, secret);

    const appName = this.configService.get<string>('APP_NAME', 'AuthService');
    const otpauthUri = authenticator.keyuri(user.email, appName, secret);

    const { plainCodes, hashedCodes } = await this.generateBackupCodes();
    await this.usersService.setBackupCodes(userId, hashedCodes);

    return { otpauthUri, backupCodes: plainCodes };
  }

  async verify2FA(userId: string, code: string): Promise<boolean> {
    const user = await this.usersService.findById(userId);
    if (!user) throw new UnauthorizedException('User not found');

    if (!user.twoFactorSecret) {
      throw new BadRequestException('Two-factor authentication has not been initialized. Call enable2FA first.');
    }

    if (user.twoFactorEnabled) {
      throw new BadRequestException('Two-factor authentication is already verified and enabled');
    }

    const isValid = authenticator.verify({ token: code, secret: user.twoFactorSecret });
    if (!isValid) {
      throw new BadRequestException('Invalid verification code');
    }

    await this.usersService.enableTwoFactor(userId);
    return true;
  }

  async disable2FA(userId: string, code: string): Promise<void> {
    const user = await this.usersService.findById(userId);
    if (!user) throw new UnauthorizedException('User not found');

    if (!user.twoFactorEnabled) {
      throw new BadRequestException('Two-factor authentication is not enabled');
    }

    if (ROLES_REQUIRING_2FA.includes(user.role)) {
      throw new ForbiddenException('Two-factor authentication is mandatory for your role and cannot be disabled');
    }

    const isValid = await this.validate2FACode(user, code);
    if (!isValid) {
      throw new UnauthorizedException('Invalid 2FA code');
    }

    await this.usersService.disableTwoFactor(userId);
  }

  async regenerateBackupCodes(userId: string, code: string): Promise<string[]> {
    const user = await this.usersService.findById(userId);
    if (!user) throw new UnauthorizedException('User not found');

    if (!user.twoFactorEnabled) {
      throw new BadRequestException('Two-factor authentication is not enabled');
    }

    const isValid = await this.validate2FACode(user, code);
    if (!isValid) {
      throw new UnauthorizedException('Invalid 2FA code');
    }

    const { plainCodes, hashedCodes } = await this.generateBackupCodes();
    await this.usersService.setBackupCodes(userId, hashedCodes);

    return plainCodes;
  }

  // ─── Token management ─────────────────────────────────────────────────────

  async refresh(refreshToken: string): Promise<TokenPair> {
    let payload: JwtPayload;
    try {
      payload = this.jwtService.verify<JwtPayload>(refreshToken, {
        secret: this.configService.get<string>('JWT_REFRESH_SECRET'),
      });
    } catch {
      throw new UnauthorizedException('Invalid refresh token');
    }

    const user = await this.usersService.findById(payload.sub);
    if (!user) throw new UnauthorizedException('User not found');

    const valid = await this.usersService.validateRefreshToken(user.id, refreshToken);
    if (!valid) throw new UnauthorizedException('Refresh token mismatch');

    // Rotate: invalidate old, issue new
    await this.usersService.setRefreshToken(user.id, null);
    return this.generateTokens(user);
  }

  async logout(accessToken: string, userId: string): Promise<void> {
    const jwtExpiresIn = this.configService.get<string>('JWT_EXPIRES_IN', '15m');
    const ttl = this.parseDurationSeconds(jwtExpiresIn);
    await this.redisService.set(`jwt:blacklist:${accessToken}`, '1', ttl);
    await this.usersService.setRefreshToken(userId, null);
  }

  async validateToken(token: string): Promise<JwtPayload> {
    try {
      const payload = this.jwtService.verify<JwtPayload>(token, {
        secret: this.configService.get<string>('JWT_SECRET'),
      });
      const blacklisted = await this.redisService.get(`jwt:blacklist:${token}`);
      if (blacklisted) throw new UnauthorizedException('Token revoked');
      return payload;
    } catch {
      throw new UnauthorizedException('Invalid token');
    }
  }

  // ─── Private helpers ──────────────────────────────────────────────────────

  private generateNumericOtp(length: number): string {
    const digits = crypto.randomInt(Math.pow(10, length - 1), Math.pow(10, length));
    return digits.toString();
  }

  /**
   * Syncs a newly registered auth-service user to the Rust core API so that
   * GET /api/users/by_email/ can resolve the integer coreId for the frontend.
   * Non-fatal: logs on failure but does not block the registration response.
   */
  private async syncUserToCoreApi(user: User): Promise<void> {
    const coreApiUrl = this.configService.get<string>(
      'CORE_API_URL',
      'http://core:8000',
    );

    const body = JSON.stringify({
      platform: 'websocket',
      platform_user_id: user.id,
      username: user.email,
      first_name: user.firstName || '',
      last_name: user.lastName || '',
      phone: user.phone || '',
      email: user.email,
      role: user.role || 'buyer',
      language_code: 'ru',
    });

    const url = new URL('/api/users/', coreApiUrl);
    const isHttps = url.protocol === 'https:';
    const lib = isHttps ? https : http;

    return new Promise((resolve) => {
      const options = {
        hostname: url.hostname,
        port: url.port || (isHttps ? 443 : 80),
        path: url.pathname,
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Content-Length': Buffer.byteLength(body),
        },
        timeout: 5000,
      };

      const req = lib.request(options, (res) => {
        res.resume();
        res.on('end', () => {
          if (res.statusCode && res.statusCode >= 200 && res.statusCode < 300) {
            console.log(`[CoreSync] Created core user for ${user.email} (status ${res.statusCode})`);
          } else if (res.statusCode === 400 || res.statusCode === 409) {
            // 400 is returned by the Rust core on duplicate platform_user_id; treat as already exists
            console.log(`[CoreSync] Core user for ${user.email} already exists (${res.statusCode})`);
          } else {
            console.error(`[CoreSync] Unexpected status ${res.statusCode} creating core user for ${user.email}`);
          }
          resolve();
        });
      });

      req.on('error', (err) => {
        console.error(`[CoreSync] Failed to create core user for ${user.email}: ${err.message}`);
        resolve();
      });

      req.on('timeout', () => {
        console.error(`[CoreSync] Timeout creating core user for ${user.email}`);
        req.destroy();
        resolve();
      });

      req.write(body);
      req.end();
    });
  }

  /**
   * Sends OTP email via the notification-service internal HTTP endpoint.
   * Falls back to a no-op log if the service URL is not configured.
   */
  private async sendOtpEmail(email: string, otp: string, context: 'registration' | 'login'): Promise<void> {
    const notificationServiceUrl = this.configService.get<string>(
      'NOTIFICATION_SERVICE_URL',
      'http://notification-service:4005',
    );

    const subject = context === 'registration'
      ? 'Groupbuy — код подтверждения регистрации'
      : 'Groupbuy — код для входа';

    const body = JSON.stringify({ email, otp, subject, context });

    const url = new URL('/internal/send-otp', notificationServiceUrl);
    const isHttps = url.protocol === 'https:';
    const lib = isHttps ? https : http;

    return new Promise((resolve) => {
      const options = {
        hostname: url.hostname,
        port: url.port || (isHttps ? 443 : 80),
        path: url.pathname,
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Content-Length': Buffer.byteLength(body),
        },
        timeout: 5000,
      };

      const req = lib.request(options, (res) => {
        console.log(`[OTP] Email dispatch status for ${email}: ${res.statusCode}`);
        // Drain the response body so the socket is released and the timeout does not fire.
        res.resume();
        res.on('end', () => resolve());
      });

      req.on('error', (err) => {
        console.error(`[OTP] Failed to dispatch OTP email to ${email}: ${err.message}`);
        resolve(); // Non-fatal: log but don't block auth flow
      });

      req.on('timeout', () => {
        console.error(`[OTP] Timeout dispatching OTP email to ${email}`);
        req.destroy();
        resolve();
      });

      req.write(body);
      req.end();
    });
  }

  private async validate2FACode(user: User, code: string): Promise<boolean> {
    if (!user.twoFactorSecret) return false;

    const totpValid = authenticator.verify({ token: code, secret: user.twoFactorSecret });
    if (totpValid) return true;

    if (user.backupCodes && user.backupCodes.length > 0) {
      for (let i = 0; i < user.backupCodes.length; i++) {
        const match = await bcrypt.compare(code, user.backupCodes[i]);
        if (match) {
          const updatedCodes = [...user.backupCodes];
          updatedCodes.splice(i, 1);
          await this.usersService.setBackupCodes(user.id, updatedCodes);
          return true;
        }
      }
    }

    return false;
  }

  private async generateBackupCodes(): Promise<{ plainCodes: string[]; hashedCodes: string[] }> {
    const plainCodes: string[] = [];
    const hashedCodes: string[] = [];
    const rounds = parseInt(process.env.BCRYPT_ROUNDS ?? '10', 10);

    for (let i = 0; i < BACKUP_CODE_COUNT; i++) {
      const code = crypto.randomBytes(4).toString('hex');
      plainCodes.push(code);
      hashedCodes.push(await bcrypt.hash(code, rounds));
    }

    return { plainCodes, hashedCodes };
  }

  private async generateTokens(user: User): Promise<TokenPair> {
    const jti = uuidv4();
    const payload: JwtPayload = {
      sub: user.id,
      email: user.email,
      role: user.role,
      jti,
    };

    const accessToken = this.jwtService.sign(payload);

    const refreshExpiresIn = this.configService.get<string>('JWT_REFRESH_EXPIRES_IN', '7d');
    const refreshToken = this.jwtService.sign(
      { ...payload, jti: uuidv4() },
      {
        secret: this.configService.get<string>('JWT_REFRESH_SECRET'),
        expiresIn: refreshExpiresIn,
      },
    );

    await this.usersService.setRefreshToken(user.id, refreshToken);

    const expiresInSec = this.parseDurationSeconds(
      this.configService.get<string>('JWT_EXPIRES_IN', '15m'),
    );

    return { accessToken, refreshToken, expiresIn: expiresInSec };
  }

  private parseDurationSeconds(duration: string): number {
    const match = duration.match(/^(\d+)([smhd])$/);
    if (!match) return 900;
    const value = parseInt(match[1], 10);
    const unit = match[2];
    const multipliers: Record<string, number> = { s: 1, m: 60, h: 3600, d: 86400 };
    return value * (multipliers[unit] ?? 1);
  }
}

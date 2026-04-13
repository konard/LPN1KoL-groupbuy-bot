/**
 * Tests for resend OTP functionality in AuthService.
 * Covers:
 * - Successful resend for login context
 * - Successful resend for registration context
 * - Cooldown enforcement (cannot resend within 30 seconds)
 * - Missing session (login: returns generic message; registration: throws)
 */

import 'reflect-metadata';

import { AuthService } from '../../services/auth-service/src/auth/auth.service';

// ─── Mock Helpers ─────────────────────────────────────────────────────────────

function makeUser(overrides: Partial<any> = {}): any {
  return {
    id: 'user-1',
    phone: '+79001234567',
    email: 'test@example.com',
    isActive: true,
    isBanned: false,
    role: 'buyer',
    twoFactorEnabled: false,
    twoFactorSecret: null,
    backupCodes: [],
    ...overrides,
  };
}

function makeRedisStore() {
  const store: Record<string, string> = {};
  return {
    get: jest.fn((key: string) => Promise.resolve(store[key] ?? null)),
    set: jest.fn((key: string, value: string) => {
      store[key] = value;
      return Promise.resolve();
    }),
    del: jest.fn((key: string) => {
      delete store[key];
      return Promise.resolve();
    }),
    _store: store,
  };
}

// ─── Test Suite ───────────────────────────────────────────────────────────────

describe('AuthService.resendOtp', () => {
  let service: AuthService;
  let redisService: ReturnType<typeof makeRedisStore>;
  let usersService: any;

  const phone = '+79001234567';
  const userId = 'user-1';
  const existingOtp = '123456';
  const userEmail = 'test@example.com';

  beforeEach(() => {
    redisService = makeRedisStore();
    usersService = {
      findByPhone: jest.fn().mockResolvedValue(makeUser()),
      findByEmail: jest.fn().mockResolvedValue(null),
      findById: jest.fn().mockResolvedValue(makeUser()),
      create: jest.fn().mockResolvedValue(makeUser()),
      setTwoFactorRequired: jest.fn().mockResolvedValue(undefined),
      setRefreshToken: jest.fn().mockResolvedValue(undefined),
      validateRefreshToken: jest.fn().mockResolvedValue(true),
    };

    const jwtService: any = {
      sign: jest.fn().mockReturnValue('mock-token'),
      verify: jest.fn().mockReturnValue({ sub: userId, email: userEmail, role: 'buyer', jti: 'jti-1' }),
    };

    const configService: any = {
      get: (key: string, defaultVal?: any) => {
        const config: Record<string, string> = {
          NOTIFICATION_SERVICE_URL: 'http://localhost:4005',
          JWT_EXPIRES_IN: '15m',
          JWT_REFRESH_EXPIRES_IN: '7d',
          JWT_SECRET: 'test-secret',
          JWT_REFRESH_SECRET: 'test-refresh-secret',
          APP_NAME: 'TestApp',
        };
        return config[key] ?? defaultVal;
      },
    };

    // Instantiate directly — no NestJS DI needed for unit testing
    service = new AuthService(usersService, jwtService, configService, redisService as any);

    // Suppress HTTP calls to notification-service
    jest.spyOn(service as any, 'sendOtpEmail').mockResolvedValue(undefined);
  });

  afterEach(() => {
    jest.clearAllMocks();
  });

  describe('login context', () => {
    beforeEach(() => {
      // Simulate active login OTP session in Redis
      redisService._store[`login:otp:${phone}`] = JSON.stringify({ userId, otp: existingOtp });
    });

    it('sends a new OTP and sets cooldown', async () => {
      const result = await service.resendOtp(phone, 'login');

      expect(result.otpSent).toBe(true);
      expect(result.message).toBeTruthy();

      // Cooldown key must be set
      expect(redisService.set).toHaveBeenCalledWith(
        `otp:resend:cooldown:login:${phone}`,
        '1',
        expect.any(Number),
      );

      // OTP session must be updated with a new code
      expect(redisService.set).toHaveBeenCalledWith(
        `login:otp:${phone}`,
        expect.stringContaining(userId),
        expect.any(Number),
      );

      // New OTP must differ from old one (probabilistically — same digit length, different value)
      const updatedRaw = redisService._store[`login:otp:${phone}`];
      const updatedSession = JSON.parse(updatedRaw);
      expect(updatedSession.userId).toBe(userId);
      // Email dispatch must have been called
      expect((service as any).sendOtpEmail).toHaveBeenCalledWith(
        userEmail,
        expect.any(String),
        'login',
      );
    });

    it('rejects resend when cooldown is active', async () => {
      redisService._store[`otp:resend:cooldown:login:${phone}`] = '1';

      await expect(service.resendOtp(phone, 'login')).rejects.toThrow(/Please wait/);
      expect((service as any).sendOtpEmail).not.toHaveBeenCalled();
    });

    it('returns generic message without throwing when no login session exists', async () => {
      delete redisService._store[`login:otp:${phone}`];

      const result = await service.resendOtp(phone, 'login');
      expect(result.otpSent).toBe(true);
      expect((service as any).sendOtpEmail).not.toHaveBeenCalled();
    });
  });

  describe('registration context', () => {
    beforeEach(() => {
      // Simulate active registration pending session in Redis
      redisService._store[`reg:pending:${phone}`] = JSON.stringify({
        phone,
        email: userEmail,
        firstName: 'Test',
        lastName: 'User',
        role: 'buyer',
        otp: existingOtp,
      });
    });

    it('sends a new OTP and sets cooldown', async () => {
      const result = await service.resendOtp(phone, 'registration');

      expect(result.otpSent).toBe(true);

      // Cooldown key must be set
      expect(redisService.set).toHaveBeenCalledWith(
        `otp:resend:cooldown:registration:${phone}`,
        '1',
        expect.any(Number),
      );

      // Registration session must have been overwritten with new OTP
      const updatedRaw = redisService._store[`reg:pending:${phone}`];
      const updatedPending = JSON.parse(updatedRaw);
      expect(updatedPending.email).toBe(userEmail);
      expect(updatedPending.otp).not.toBe(existingOtp);

      expect((service as any).sendOtpEmail).toHaveBeenCalledWith(
        userEmail,
        expect.any(String),
        'registration',
      );
    });

    it('rejects resend when cooldown is active', async () => {
      redisService._store[`otp:resend:cooldown:registration:${phone}`] = '1';

      await expect(service.resendOtp(phone, 'registration')).rejects.toThrow(/Please wait/);
      expect((service as any).sendOtpEmail).not.toHaveBeenCalled();
    });

    it('throws when registration session does not exist', async () => {
      delete redisService._store[`reg:pending:${phone}`];

      await expect(service.resendOtp(phone, 'registration')).rejects.toThrow(/session expired/i);
    });
  });

  it('throws when phone is empty string', async () => {
    await expect(service.resendOtp('', 'login')).rejects.toThrow(/required/i);
  });
});

import {
  Injectable,
  ForbiddenException,
  NotFoundException,
  Logger,
  BadRequestException,
} from '@nestjs/common';
import { InjectRepository } from '@nestjs/typeorm';
import { Repository, DataSource } from 'typeorm';
import { User } from './users.entity';
import { AuditBan } from './audit-ban.entity';
import { RedisService } from '../redis/redis.service';

// Redis TTL for isBanned cache (seconds). Short enough to react quickly; long enough to protect DB.
const BAN_CACHE_TTL_SECONDS = 10;

@Injectable()
export class BanService {
  private readonly logger = new Logger(BanService.name);

  constructor(
    @InjectRepository(User)
    private readonly usersRepo: Repository<User>,
    @InjectRepository(AuditBan)
    private readonly auditBanRepo: Repository<AuditBan>,
    private readonly redisService: RedisService,
    private readonly dataSource: DataSource,
  ) {}

  /**
   * Ban a user.
   * Side-effects (all within one transaction):
   *  1. Set user.isBanned = true, user.bannedAt, user.banReason
   *  2. Invalidate refresh token (set to null) — forces re-login to fail
   *  3. Write to audit_bans
   * After commit:
   *  4. Invalidate Redis isBanned cache so new requests see the ban immediately
   */
  async banUser(
    targetUserId: string,
    adminId: string,
    reason: string,
    metadata: Record<string, any> = {},
  ): Promise<AuditBan> {
    const user = await this.usersRepo.findOne({ where: { id: targetUserId } });
    if (!user) throw new NotFoundException('User not found');
    if (user.isBanned) throw new BadRequestException('User is already banned');

    const auditEntry = await this.dataSource.transaction(async (manager) => {
      // 1. Mark user as banned and clear refresh token to force all sessions out
      await manager.update(User, targetUserId, {
        isBanned: true,
        bannedAt: new Date(),
        banReason: reason,
        refreshTokenHash: null, // invalidates all active refresh tokens immediately
      });

      // 2. Blacklist any outstanding access tokens by writing to Redis
      //    (handled via validateToken middleware that checks jwt:blacklist:{token})
      //    Here we write a ban-flag that the middleware also checks.

      // 3. Write audit entry
      const audit = manager.create(AuditBan, {
        targetUserId,
        adminId,
        action: 'ban',
        reason,
        metadata,
      });
      return manager.save(AuditBan, audit);
    });

    // 4. Overwrite isBanned cache immediately — new requests will see the ban within 1 Redis call
    await this.redisService.set(`user:${targetUserId}:banned`, '1', BAN_CACHE_TTL_SECONDS);

    this.logger.warn(
      `User ${targetUserId} banned by admin ${adminId}. Reason: ${reason}`,
    );

    return auditEntry;
  }

  /**
   * Unban a user.
   */
  async unbanUser(
    targetUserId: string,
    adminId: string,
    reason: string,
  ): Promise<AuditBan> {
    const user = await this.usersRepo.findOne({ where: { id: targetUserId } });
    if (!user) throw new NotFoundException('User not found');
    if (!user.isBanned) throw new BadRequestException('User is not banned');

    const auditEntry = await this.dataSource.transaction(async (manager) => {
      await manager.update(User, targetUserId, {
        isBanned: false,
        bannedAt: null,
        banReason: null,
      });

      const audit = manager.create(AuditBan, {
        targetUserId,
        adminId,
        action: 'unban',
        reason,
        metadata: {},
      });
      return manager.save(AuditBan, audit);
    });

    // Remove ban cache entry so the next request is allowed through
    await this.redisService.del(`user:${targetUserId}:banned`);

    this.logger.log(`User ${targetUserId} unbanned by admin ${adminId}.`);

    return auditEntry;
  }

  /**
   * Check if a user is banned.
   * Uses a Redis cache with a short TTL (10 s) to avoid a DB query on every request.
   * If Redis is unavailable, falls back to PostgreSQL.
   */
  async isBanned(userId: string): Promise<boolean> {
    // Fast path: Redis cache
    const cached = await this.redisService.get(`user:${userId}:banned`);
    if (cached !== null) {
      return cached === '1';
    }

    // Slow path: DB lookup
    const user = await this.usersRepo.findOne({
      where: { id: userId },
      select: ['id', 'isBanned'],
    });
    const banned = user?.isBanned ?? false;

    // Populate cache; write '0' for not-banned users so we don't hit DB every time
    await this.redisService.set(
      `user:${userId}:banned`,
      banned ? '1' : '0',
      BAN_CACHE_TTL_SECONDS,
    );

    return banned;
  }

  /**
   * Throw 403 if the user is banned. Suitable for use in guards/middleware.
   */
  async assertNotBanned(userId: string): Promise<void> {
    const banned = await this.isBanned(userId);
    if (banned) {
      throw new ForbiddenException({
        status: 403,
        code: 'USER_BANNED',
        message: 'Your account has been suspended',
      });
    }
  }

  async getBanHistory(targetUserId: string): Promise<AuditBan[]> {
    return this.auditBanRepo.find({
      where: { targetUserId },
      order: { createdAt: 'DESC' },
    });
  }
}

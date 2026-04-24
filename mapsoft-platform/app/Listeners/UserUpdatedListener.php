<?php

namespace App\Listeners;

use App\Contracts\Infrastructure\CacheInterface;

final class UserUpdatedListener
{
    public function __construct(
        private readonly CacheInterface $cache
    ) {
    }

    public function handle(object $event): void
    {
        $uuid = $event->uuid ?? null;

        if (is_string($uuid)) {
            $this->cache->forget('users:profile:' . $uuid);
        }

        $this->cache->tags(['users'])->flushByTag('users');
    }
}

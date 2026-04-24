<?php

namespace App\Listeners;

use App\Contracts\Infrastructure\CacheInterface;

final class TariffChangedListener
{
    public function __construct(
        private readonly CacheInterface $cache
    ) {
    }

    public function handle(object $event): void
    {
        $this->cache->forget('tariffs:active');
        $this->cache->tags(['tariffs'])->flushByTag('tariffs');
    }
}

<?php

namespace App\Contracts\Infrastructure;

interface CacheInterface
{
    public function get(string $key): mixed;

    public function put(string $key, mixed $value, int $ttl): void;

    public function forget(string $key): void;

    public function tags(array $tags): self;

    public function flushByTag(string $tag): void;
}

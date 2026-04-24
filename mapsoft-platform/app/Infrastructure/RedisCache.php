<?php

namespace App\Infrastructure;

use App\Contracts\Infrastructure\CacheInterface;

final class RedisCache implements CacheInterface
{
    private array $tags = [];

    public function __construct(
        private readonly mixed $redis
    ) {
    }

    public function get(string $key): mixed
    {
        $value = $this->redis->get($key);

        if (is_string($value)) {
            $decoded = json_decode($value, true);
            return json_last_error() === JSON_ERROR_NONE ? $decoded : $value;
        }

        return $value;
    }

    public function put(string $key, mixed $value, int $ttl): void
    {
        $this->redis->setex($key, $ttl, json_encode($value, JSON_THROW_ON_ERROR));

        foreach ($this->tags as $tag) {
            $this->redis->sadd('tag:' . $tag, [$key]);
        }
    }

    public function forget(string $key): void
    {
        $this->redis->del([$key]);
    }

    public function tags(array $tags): self
    {
        $clone = clone $this;
        $clone->tags = $tags;

        return $clone;
    }

    public function flushByTag(string $tag): void
    {
        $keys = $this->redis->smembers('tag:' . $tag);

        if ($keys !== []) {
            $this->redis->del($keys);
        }

        $this->redis->del(['tag:' . $tag]);
    }
}

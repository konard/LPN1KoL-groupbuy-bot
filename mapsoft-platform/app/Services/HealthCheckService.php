<?php

namespace App\Services;

use App\Contracts\Infrastructure\CacheInterface;
use App\Contracts\Infrastructure\HttpClientInterface;
use App\Contracts\Infrastructure\MessageBrokerInterface;
use App\Contracts\Infrastructure\TransactionManagerInterface;
use App\DTO\HealthCheckResultDTO;
use Throwable;

final class HealthCheckService
{
    public function __construct(
        private readonly CacheInterface $cache,
        private readonly MessageBrokerInterface $broker,
        private readonly HttpClientInterface $client,
        private readonly TransactionManagerInterface $transaction
    ) {
    }

    public function check(): HealthCheckResultDTO
    {
        return new HealthCheckResultDTO([
            'database' => $this->checkDatabase(),
            'redis' => $this->checkRedis(),
            'rabbitmq' => $this->checkRabbitMq(),
            'http' => $this->checkHttp(),
        ]);
    }

    private function checkDatabase(): array
    {
        try {
            $this->transaction->beginTransaction();
            $this->transaction->rollBack();
            return ['status' => 'ok'];
        } catch (Throwable $exception) {
            return ['status' => 'down', 'message' => $exception->getMessage()];
        }
    }

    private function checkRedis(): array
    {
        try {
            $this->cache->put('health:redis', 'ok', 10);
            return ['status' => $this->cache->get('health:redis') === 'ok' ? 'ok' : 'down'];
        } catch (Throwable $exception) {
            return ['status' => 'down', 'message' => $exception->getMessage()];
        }
    }

    private function checkRabbitMq(): array
    {
        try {
            $this->broker->publish('health', 'health.check', ['status' => 'ok']);
            return ['status' => 'ok'];
        } catch (Throwable $exception) {
            return ['status' => 'down', 'message' => $exception->getMessage()];
        }
    }

    private function checkHttp(): array
    {
        try {
            $this->client->get('http://localhost/health', []);
            return ['status' => 'ok'];
        } catch (Throwable $exception) {
            return ['status' => 'down', 'message' => $exception->getMessage()];
        }
    }
}

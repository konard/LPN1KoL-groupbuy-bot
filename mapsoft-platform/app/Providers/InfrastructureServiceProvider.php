<?php

namespace App\Providers;

use App\Contracts\Infrastructure\CacheInterface;
use App\Contracts\Infrastructure\HttpClientInterface;
use App\Contracts\Infrastructure\MessageBrokerInterface;
use App\Contracts\Infrastructure\TransactionManagerInterface;
use App\Infrastructure\DatabaseTransactionManager;
use App\Infrastructure\HttpGuzzleClient;
use App\Infrastructure\RabbitMQBroker;
use App\Infrastructure\RedisCache;
use GuzzleHttp\Client;
use Illuminate\Database\ConnectionInterface;
use Illuminate\Support\ServiceProvider;
use PhpAmqpLib\Connection\AMQPStreamConnection;

final class InfrastructureServiceProvider extends ServiceProvider
{
    public function register(): void
    {
        $this->app->bind(CacheInterface::class, function ($app): RedisCache {
            return new RedisCache($app->make('redis')->connection());
        });

        $this->app->bind(HttpClientInterface::class, function (): HttpGuzzleClient {
            return new HttpGuzzleClient(new Client([
                'timeout' => 5,
            ]));
        });

        $this->app->bind(MessageBrokerInterface::class, function (): RabbitMQBroker {
            $connection = new AMQPStreamConnection(
                env('RABBITMQ_HOST', '127.0.0.1'),
                (int) env('RABBITMQ_PORT', 5672),
                env('RABBITMQ_USER', 'guest'),
                env('RABBITMQ_PASSWORD', 'guest')
            );

            return new RabbitMQBroker($connection->channel());
        });

        $this->app->bind(TransactionManagerInterface::class, function ($app): DatabaseTransactionManager {
            return new DatabaseTransactionManager($app->make(ConnectionInterface::class));
        });
    }
}

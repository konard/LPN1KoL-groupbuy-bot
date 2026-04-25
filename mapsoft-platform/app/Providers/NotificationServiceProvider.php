<?php

namespace App\Providers;

use App\Contracts\NotificationHandlerInterface;
use App\Services\EmailNotificationHandler;
use App\Services\NotificationDispatchService;
use App\Services\PushNotificationHandler;
use App\Services\SmsNotificationHandler;
use Illuminate\Support\ServiceProvider;

final class NotificationServiceProvider extends ServiceProvider
{
    public function register(): void
    {
        $handlers = [
            EmailNotificationHandler::class,
            SmsNotificationHandler::class,
            PushNotificationHandler::class,
        ];

        foreach ($handlers as $handler) {
            $this->app->bind($handler);
        }

        $this->app->tag($handlers, NotificationHandlerInterface::class);

        $this->app->bind(NotificationDispatchService::class, function ($app): NotificationDispatchService {
            return new NotificationDispatchService(
                $app->make(\App\Contracts\Infrastructure\MessageBrokerInterface::class),
                $app->make(\App\Contracts\Repositories\NotificationLogWriterInterface::class),
                iterator_to_array($app->tagged(NotificationHandlerInterface::class))
            );
        });
    }
}

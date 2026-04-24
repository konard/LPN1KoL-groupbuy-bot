<?php

namespace App\Services;

use App\Contracts\Infrastructure\MessageBrokerInterface;
use App\Contracts\NotificationHandlerInterface;
use App\Contracts\Repositories\NotificationLogWriterInterface;
use App\DTO\CreateNotificationLogDTO;
use App\DTO\NotificationDTO;
use App\Exceptions\NotificationDispatchException;
use Throwable;

final class NotificationDispatchService
{
    public function __construct(
        private readonly MessageBrokerInterface $broker,
        private readonly NotificationLogWriterInterface $logs,
        private readonly array $handlers
    ) {
    }

    public function dispatch(NotificationDTO $notification): void
    {
        try {
            foreach ($this->handlers as $handler) {
                if ($handler instanceof NotificationHandlerInterface && $handler->supports($notification->type())) {
                    $handler->handle($notification);
                    $this->logs->log(new CreateNotificationLogDTO(
                        $notification->userId(),
                        $notification->type(),
                        $notification->channel(),
                        'sent',
                        $notification->payload()
                    ));
                    return;
                }
            }

            $this->broker->publish('notifications', $notification->type()->value, $notification->toArray());
            $this->logs->log(new CreateNotificationLogDTO(
                $notification->userId(),
                $notification->type(),
                $notification->channel(),
                'queued',
                $notification->payload()
            ));
        } catch (Throwable $exception) {
            $this->logs->log(new CreateNotificationLogDTO(
                $notification->userId(),
                $notification->type(),
                $notification->channel(),
                'failed',
                $notification->payload()
            ));
            throw new NotificationDispatchException($exception->getMessage(), 0, $exception);
        }
    }
}

<?php

namespace App\Services;

use App\Contracts\Infrastructure\HttpClientInterface;
use App\Contracts\NotificationHandlerInterface;
use App\DTO\NotificationDTO;
use App\Enums\NotificationChannel;
use App\Enums\NotificationType;

final class EmailNotificationHandler implements NotificationHandlerInterface
{
    public function __construct(
        private readonly HttpClientInterface $client
    ) {
    }

    public function handle(NotificationDTO $notification): void
    {
        $this->client->post('/email/send', $notification->payload(), []);
    }

    public function supports(NotificationType $type): bool
    {
        return in_array($type, [NotificationType::BillNew, NotificationType::BillOverdue, NotificationType::TariffChanged], true);
    }
}

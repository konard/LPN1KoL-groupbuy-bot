<?php

namespace App\Services;

use App\Contracts\Infrastructure\HttpClientInterface;
use App\Contracts\NotificationHandlerInterface;
use App\DTO\NotificationDTO;
use App\Enums\NotificationType;

final class SmsNotificationHandler implements NotificationHandlerInterface
{
    public function __construct(
        private readonly HttpClientInterface $client
    ) {
    }

    public function handle(NotificationDTO $notification): void
    {
        $this->client->post('/sms/send', $notification->payload(), []);
    }

    public function supports(NotificationType $type): bool
    {
        return $type === NotificationType::BillOverdue;
    }
}

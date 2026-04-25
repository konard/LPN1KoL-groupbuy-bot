<?php

namespace App\Contracts;

use App\DTO\NotificationDTO;
use App\Enums\NotificationType;

interface NotificationHandlerInterface
{
    public function handle(NotificationDTO $notification): void;

    public function supports(NotificationType $type): bool;
}

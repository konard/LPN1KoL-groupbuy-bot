<?php

namespace App\Contracts\Repositories;

use App\DTO\CreateNotificationLogDTO;
use App\DTO\NotificationLogDTO;

interface NotificationLogWriterInterface
{
    public function log(CreateNotificationLogDTO $dto): NotificationLogDTO;
}

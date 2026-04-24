<?php

namespace App\Repositories;

use App\Contracts\Repositories\NotificationLogWriterInterface;
use App\DTO\CreateNotificationLogDTO;
use App\DTO\NotificationLogDTO;
use App\Models\Notification;

final class EloquentNotificationLogRepository implements NotificationLogWriterInterface
{
    public function __construct(
        private readonly Notification $model
    ) {
    }

    public function log(CreateNotificationLogDTO $dto): NotificationLogDTO
    {
        $notification = $this->model->newQuery()->create([
            'user_id' => $dto->userId(),
            'type' => $dto->type()->value,
            'channel' => $dto->channel()->value,
            'status' => $dto->status(),
            'payload_json' => $dto->payload(),
        ]);

        return NotificationLogDTO::fromArray([
            'id' => $notification->id,
            'user_id' => $notification->user_id,
            'type' => $notification->type,
            'channel' => $notification->channel,
            'status' => $notification->status,
            'payload' => $notification->payload_json ?? [],
            'created_at' => $notification->created_at,
        ]);
    }
}

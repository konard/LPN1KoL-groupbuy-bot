<?php

namespace App\DTO;

use App\Enums\NotificationChannel;
use App\Enums\NotificationType;
use Webmozart\Assert\Assert;

final class NotificationDTO
{
    public function __construct(
        private readonly int $id,
        private readonly int $userId,
        private readonly NotificationType $type,
        private readonly NotificationChannel $channel,
        private readonly array $payload
    ) {
        Assert::greaterThanEq($this->id, 0);
        Assert::positiveInteger($this->userId);
    }

    public function id(): int
    {
        return $this->id;
    }

    public function userId(): int
    {
        return $this->userId;
    }

    public function type(): NotificationType
    {
        return $this->type;
    }

    public function channel(): NotificationChannel
    {
        return $this->channel;
    }

    public function payload(): array
    {
        return $this->payload;
    }

    public function toArray(): array
    {
        return [
            'id' => $this->id,
            'user_id' => $this->userId,
            'type' => $this->type->value,
            'channel' => $this->channel->value,
            'payload' => $this->payload,
        ];
    }

    public static function fromArray(array $data): static
    {
        return new static(
            (int) $data['id'],
            (int) $data['user_id'],
            NotificationType::from((string) $data['type']),
            NotificationChannel::from((string) $data['channel']),
            $data['payload'] ?? []
        );
    }
}

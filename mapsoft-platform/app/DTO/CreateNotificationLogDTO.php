<?php

namespace App\DTO;

use App\Enums\NotificationChannel;
use App\Enums\NotificationType;
use Webmozart\Assert\Assert;

final class CreateNotificationLogDTO
{
    public function __construct(
        private readonly int $userId,
        private readonly NotificationType $type,
        private readonly NotificationChannel $channel,
        private readonly string $status,
        private readonly array $payload
    ) {
        Assert::positiveInteger($this->userId);
        Assert::notEmpty($this->status);
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

    public function status(): string
    {
        return $this->status;
    }

    public function payload(): array
    {
        return $this->payload;
    }

    public function toArray(): array
    {
        return [
            'user_id' => $this->userId,
            'type' => $this->type->value,
            'channel' => $this->channel->value,
            'status' => $this->status,
            'payload' => $this->payload,
        ];
    }

    public static function fromArray(array $data): static
    {
        return new static(
            (int) $data['user_id'],
            NotificationType::from((string) $data['type']),
            NotificationChannel::from((string) $data['channel']),
            (string) $data['status'],
            $data['payload'] ?? []
        );
    }
}

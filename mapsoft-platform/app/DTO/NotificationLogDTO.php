<?php

namespace App\DTO;

use App\Enums\NotificationChannel;
use App\Enums\NotificationType;
use Carbon\CarbonImmutable;
use Carbon\CarbonInterface;
use Webmozart\Assert\Assert;

final class NotificationLogDTO
{
    public function __construct(
        private readonly int $id,
        private readonly int $userId,
        private readonly NotificationType $type,
        private readonly NotificationChannel $channel,
        private readonly string $status,
        private readonly array $payload,
        private readonly CarbonInterface $createdAt
    ) {
        Assert::positiveInteger($this->id);
        Assert::positiveInteger($this->userId);
        Assert::notEmpty($this->status);
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

    public function status(): string
    {
        return $this->status;
    }

    public function payload(): array
    {
        return $this->payload;
    }

    public function createdAt(): CarbonInterface
    {
        return $this->createdAt;
    }

    public function toArray(): array
    {
        return [
            'id' => $this->id,
            'user_id' => $this->userId,
            'type' => $this->type->value,
            'channel' => $this->channel->value,
            'status' => $this->status,
            'payload' => $this->payload,
            'created_at' => $this->createdAt->toIso8601String(),
        ];
    }

    public static function fromArray(array $data): static
    {
        return new static(
            (int) $data['id'],
            (int) $data['user_id'],
            NotificationType::from((string) $data['type']),
            NotificationChannel::from((string) $data['channel']),
            (string) $data['status'],
            $data['payload'] ?? [],
            CarbonImmutable::parse($data['created_at'])
        );
    }
}

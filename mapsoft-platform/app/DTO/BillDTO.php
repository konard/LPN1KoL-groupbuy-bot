<?php

namespace App\DTO;

use App\Enums\BillStatus;
use Carbon\CarbonImmutable;
use Carbon\CarbonInterface;
use Webmozart\Assert\Assert;

final class BillDTO
{
    public function __construct(
        private readonly int $id,
        private readonly string $uuid,
        private readonly int $userId,
        private readonly float $amount,
        private readonly BillStatus $status,
        private readonly string $billingPeriod,
        private readonly CarbonInterface $dueDate,
        private readonly ?CarbonInterface $paidAt,
        private readonly array $items
    ) {
        Assert::greaterThanEq($this->id, 0);
        Assert::uuid($this->uuid);
        Assert::positiveInteger($this->userId);
        Assert::greaterThanEq($this->amount, 0);
        Assert::allIsInstanceOf($this->items, BillItemDTO::class);
    }

    public function id(): int
    {
        return $this->id;
    }

    public function uuid(): string
    {
        return $this->uuid;
    }

    public function userId(): int
    {
        return $this->userId;
    }

    public function amount(): float
    {
        return $this->amount;
    }

    public function status(): BillStatus
    {
        return $this->status;
    }

    public function billingPeriod(): string
    {
        return $this->billingPeriod;
    }

    public function dueDate(): CarbonInterface
    {
        return $this->dueDate;
    }

    public function paidAt(): ?CarbonInterface
    {
        return $this->paidAt;
    }

    public function items(): array
    {
        return $this->items;
    }

    public function toArray(): array
    {
        return [
            'id' => $this->id,
            'uuid' => $this->uuid,
            'user_id' => $this->userId,
            'amount' => $this->amount,
            'status' => $this->status->value,
            'billing_period' => $this->billingPeriod,
            'due_date' => $this->dueDate->toDateString(),
            'paid_at' => $this->paidAt?->toIso8601String(),
            'items' => array_map(static fn (BillItemDTO $item): array => $item->toArray(), $this->items),
        ];
    }

    public static function fromArray(array $data): static
    {
        return new static(
            (int) $data['id'],
            (string) $data['uuid'],
            (int) $data['user_id'],
            (float) $data['amount'],
            BillStatus::from((string) $data['status']),
            (string) $data['billing_period'],
            CarbonImmutable::parse($data['due_date']),
            isset($data['paid_at']) ? CarbonImmutable::parse($data['paid_at']) : null,
            array_map(static fn (array $item): BillItemDTO => BillItemDTO::fromArray($item), $data['items'] ?? [])
        );
    }
}

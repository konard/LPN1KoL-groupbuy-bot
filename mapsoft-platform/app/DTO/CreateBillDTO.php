<?php

namespace App\DTO;

use Carbon\CarbonImmutable;
use Carbon\CarbonInterface;
use Webmozart\Assert\Assert;

final class CreateBillDTO
{
    public function __construct(
        private readonly int $userId,
        private readonly float $amount,
        private readonly string $billingPeriod,
        private readonly CarbonInterface $dueDate,
        private readonly array $items
    ) {
        Assert::positiveInteger($this->userId);
        Assert::greaterThanEq($this->amount, 0);
        Assert::notEmpty($this->billingPeriod);
        Assert::allIsInstanceOf($this->items, BillItemDTO::class);
    }

    public function userId(): int
    {
        return $this->userId;
    }

    public function amount(): float
    {
        return $this->amount;
    }

    public function billingPeriod(): string
    {
        return $this->billingPeriod;
    }

    public function dueDate(): CarbonInterface
    {
        return $this->dueDate;
    }

    public function items(): array
    {
        return $this->items;
    }

    public function toArray(): array
    {
        return [
            'user_id' => $this->userId,
            'amount' => $this->amount,
            'billing_period' => $this->billingPeriod,
            'due_date' => $this->dueDate->toDateString(),
            'items' => array_map(static fn (BillItemDTO $item): array => $item->toArray(), $this->items),
        ];
    }

    public static function fromArray(array $data): static
    {
        return new static(
            (int) $data['user_id'],
            (float) $data['amount'],
            (string) $data['billing_period'],
            CarbonImmutable::parse($data['due_date']),
            array_map(static fn (array $item): BillItemDTO => BillItemDTO::fromArray($item), $data['items'] ?? [])
        );
    }
}

<?php

namespace App\DTO;

use Webmozart\Assert\Assert;

final class BillItemDTO
{
    public function __construct(
        private readonly int $id,
        private readonly int $billId,
        private readonly int $readingId,
        private readonly float $consumption,
        private readonly float $pricePerUnit,
        private readonly float $subtotal
    ) {
        Assert::greaterThanEq($this->id, 0);
        Assert::greaterThanEq($this->billId, 0);
        Assert::positiveInteger($this->readingId);
        Assert::greaterThanEq($this->consumption, 0);
        Assert::greaterThanEq($this->pricePerUnit, 0);
        Assert::greaterThanEq($this->subtotal, 0);
    }

    public function id(): int
    {
        return $this->id;
    }

    public function billId(): int
    {
        return $this->billId;
    }

    public function readingId(): int
    {
        return $this->readingId;
    }

    public function consumption(): float
    {
        return $this->consumption;
    }

    public function pricePerUnit(): float
    {
        return $this->pricePerUnit;
    }

    public function subtotal(): float
    {
        return $this->subtotal;
    }

    public function toArray(): array
    {
        return [
            'id' => $this->id,
            'bill_id' => $this->billId,
            'reading_id' => $this->readingId,
            'consumption' => $this->consumption,
            'price_per_unit' => $this->pricePerUnit,
            'subtotal' => $this->subtotal,
        ];
    }

    public static function fromArray(array $data): static
    {
        return new static(
            (int) $data['id'],
            (int) $data['bill_id'],
            (int) $data['reading_id'],
            (float) $data['consumption'],
            (float) $data['price_per_unit'],
            (float) $data['subtotal']
        );
    }
}

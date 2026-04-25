<?php

namespace App\DTO;

use App\Enums\Currency;
use Webmozart\Assert\Assert;

final class MoneyDTO
{
    public function __construct(
        private readonly float $amount,
        private readonly Currency $currency
    ) {
        Assert::greaterThanEq($this->amount, 0);
    }

    public function amount(): float
    {
        return $this->amount;
    }

    public function currency(): Currency
    {
        return $this->currency;
    }

    public function toArray(): array
    {
        return [
            'amount' => $this->amount,
            'currency' => $this->currency->value,
        ];
    }

    public static function fromArray(array $data): static
    {
        return new static(
            (float) $data['amount'],
            Currency::from((string) $data['currency'])
        );
    }
}

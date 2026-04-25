<?php

namespace App\DTO;

use App\Enums\Currency;
use Carbon\CarbonImmutable;
use Carbon\CarbonInterface;
use Webmozart\Assert\Assert;

final class TariffDTO
{
    public function __construct(
        private readonly int $id,
        private readonly string $name,
        private readonly float $pricePerUnit,
        private readonly Currency $currency,
        private readonly CarbonInterface $activeFrom,
        private readonly ?CarbonInterface $activeTo
    ) {
        Assert::positiveInteger($this->id);
        Assert::notEmpty($this->name);
        Assert::greaterThanEq($this->pricePerUnit, 0);
    }

    public function id(): int
    {
        return $this->id;
    }

    public function name(): string
    {
        return $this->name;
    }

    public function pricePerUnit(): float
    {
        return $this->pricePerUnit;
    }

    public function currency(): Currency
    {
        return $this->currency;
    }

    public function activeFrom(): CarbonInterface
    {
        return $this->activeFrom;
    }

    public function activeTo(): ?CarbonInterface
    {
        return $this->activeTo;
    }

    public function toArray(): array
    {
        return [
            'id' => $this->id,
            'name' => $this->name,
            'price_per_unit' => $this->pricePerUnit,
            'currency' => $this->currency->value,
            'active_from' => $this->activeFrom->toDateString(),
            'active_to' => $this->activeTo?->toDateString(),
        ];
    }

    public static function fromArray(array $data): static
    {
        return new static(
            (int) $data['id'],
            (string) $data['name'],
            (float) $data['price_per_unit'],
            Currency::from((string) $data['currency']),
            CarbonImmutable::parse($data['active_from']),
            isset($data['active_to']) ? CarbonImmutable::parse($data['active_to']) : null
        );
    }
}

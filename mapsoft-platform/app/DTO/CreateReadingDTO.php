<?php

namespace App\DTO;

use App\Enums\ReadingType;
use Carbon\CarbonImmutable;
use Carbon\CarbonInterface;
use Webmozart\Assert\Assert;

final class CreateReadingDTO
{
    public function __construct(
        private readonly int $userId,
        private readonly ReadingType $type,
        private readonly float $value,
        private readonly CarbonInterface $periodStart,
        private readonly CarbonInterface $periodEnd,
        private readonly string $idempotencyKey
    ) {
        Assert::positiveInteger($this->userId);
        Assert::greaterThanEq($this->value, 0);
        Assert::notEmpty($this->idempotencyKey);
        Assert::lessThanEq($this->periodStart->getTimestamp(), $this->periodEnd->getTimestamp());
    }

    public function userId(): int
    {
        return $this->userId;
    }

    public function type(): ReadingType
    {
        return $this->type;
    }

    public function value(): float
    {
        return $this->value;
    }

    public function periodStart(): CarbonInterface
    {
        return $this->periodStart;
    }

    public function periodEnd(): CarbonInterface
    {
        return $this->periodEnd;
    }

    public function idempotencyKey(): string
    {
        return $this->idempotencyKey;
    }

    public function toArray(): array
    {
        return [
            'user_id' => $this->userId,
            'type' => $this->type->value,
            'value' => $this->value,
            'period_start' => $this->periodStart->toDateString(),
            'period_end' => $this->periodEnd->toDateString(),
            'idempotency_key' => $this->idempotencyKey,
        ];
    }

    public static function fromArray(array $data): static
    {
        return new static(
            (int) $data['user_id'],
            ReadingType::from((string) $data['type']),
            (float) $data['value'],
            CarbonImmutable::parse($data['period_start']),
            CarbonImmutable::parse($data['period_end']),
            (string) $data['idempotency_key']
        );
    }
}

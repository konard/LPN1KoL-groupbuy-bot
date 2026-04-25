<?php

namespace App\DTO;

use App\Enums\ReadingType;
use Carbon\CarbonImmutable;
use Carbon\CarbonInterface;
use Webmozart\Assert\Assert;

final class ReadingDTO
{
    public function __construct(
        private readonly int $id,
        private readonly int $userId,
        private readonly ReadingType $type,
        private readonly float $value,
        private readonly CarbonInterface $periodStart,
        private readonly CarbonInterface $periodEnd,
        private readonly CarbonInterface $submittedAt
    ) {
        Assert::greaterThanEq($this->id, 0);
        Assert::positiveInteger($this->userId);
        Assert::greaterThanEq($this->value, 0);
        Assert::lessThanEq($this->periodStart->getTimestamp(), $this->periodEnd->getTimestamp());
    }

    public function id(): int
    {
        return $this->id;
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

    public function submittedAt(): CarbonInterface
    {
        return $this->submittedAt;
    }

    public function toArray(): array
    {
        return [
            'id' => $this->id,
            'user_id' => $this->userId,
            'type' => $this->type->value,
            'value' => $this->value,
            'period_start' => $this->periodStart->toDateString(),
            'period_end' => $this->periodEnd->toDateString(),
            'submitted_at' => $this->submittedAt->toIso8601String(),
        ];
    }

    public static function fromArray(array $data): static
    {
        return new static(
            (int) $data['id'],
            (int) $data['user_id'],
            ReadingType::from((string) $data['type']),
            (float) $data['value'],
            CarbonImmutable::parse($data['period_start']),
            CarbonImmutable::parse($data['period_end']),
            CarbonImmutable::parse($data['submitted_at'])
        );
    }
}

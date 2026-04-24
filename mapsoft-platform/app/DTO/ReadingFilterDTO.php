<?php

namespace App\DTO;

use App\Enums\ReadingType;
use Carbon\CarbonImmutable;
use Carbon\CarbonInterface;
use Webmozart\Assert\Assert;

final class ReadingFilterDTO
{
    public function __construct(
        private readonly int $userId,
        private readonly ?ReadingType $type,
        private readonly ?CarbonInterface $dateFrom,
        private readonly ?CarbonInterface $dateTo,
        private readonly ?string $cursor,
        private readonly int $limit
    ) {
        Assert::positiveInteger($this->userId);
        Assert::range($this->limit, 1, 500);
    }

    public function userId(): int
    {
        return $this->userId;
    }

    public function type(): ?ReadingType
    {
        return $this->type;
    }

    public function dateFrom(): ?CarbonInterface
    {
        return $this->dateFrom;
    }

    public function dateTo(): ?CarbonInterface
    {
        return $this->dateTo;
    }

    public function cursor(): ?string
    {
        return $this->cursor;
    }

    public function limit(): int
    {
        return $this->limit;
    }

    public function toArray(): array
    {
        return [
            'user_id' => $this->userId,
            'type' => $this->type?->value,
            'date_from' => $this->dateFrom?->toDateString(),
            'date_to' => $this->dateTo?->toDateString(),
            'cursor' => $this->cursor,
            'limit' => $this->limit,
        ];
    }

    public static function fromArray(array $data): static
    {
        return new static(
            (int) $data['user_id'],
            isset($data['type']) ? ReadingType::from((string) $data['type']) : null,
            isset($data['date_from']) ? CarbonImmutable::parse($data['date_from']) : null,
            isset($data['date_to']) ? CarbonImmutable::parse($data['date_to']) : null,
            $data['cursor'] ?? null,
            (int) ($data['limit'] ?? 50)
        );
    }
}

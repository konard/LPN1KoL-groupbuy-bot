<?php

namespace App\DTO;

use App\Enums\BillStatus;
use Carbon\CarbonImmutable;
use Carbon\CarbonInterface;
use Webmozart\Assert\Assert;

final class BillFilterDTO
{
    public function __construct(
        private readonly int $userId,
        private readonly ?BillStatus $status,
        private readonly ?CarbonInterface $dateFrom,
        private readonly ?CarbonInterface $dateTo,
        private readonly int $perPage
    ) {
        Assert::positiveInteger($this->userId);
        Assert::range($this->perPage, 1, 500);
    }

    public function userId(): int
    {
        return $this->userId;
    }

    public function status(): ?BillStatus
    {
        return $this->status;
    }

    public function dateFrom(): ?CarbonInterface
    {
        return $this->dateFrom;
    }

    public function dateTo(): ?CarbonInterface
    {
        return $this->dateTo;
    }

    public function perPage(): int
    {
        return $this->perPage;
    }

    public function toArray(): array
    {
        return [
            'user_id' => $this->userId,
            'status' => $this->status?->value,
            'date_from' => $this->dateFrom?->toDateString(),
            'date_to' => $this->dateTo?->toDateString(),
            'per_page' => $this->perPage,
        ];
    }

    public static function fromArray(array $data): static
    {
        return new static(
            (int) $data['user_id'],
            isset($data['status']) ? BillStatus::from((string) $data['status']) : null,
            isset($data['date_from']) ? CarbonImmutable::parse($data['date_from']) : null,
            isset($data['date_to']) ? CarbonImmutable::parse($data['date_to']) : null,
            (int) ($data['per_page'] ?? 50)
        );
    }
}

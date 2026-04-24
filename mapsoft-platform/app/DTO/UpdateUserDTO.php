<?php

namespace App\DTO;

use Webmozart\Assert\Assert;

final class UpdateUserDTO
{
    public function __construct(
        private readonly string $name,
        private readonly string $email,
        private readonly ?string $phone,
        private readonly int $tariffId,
        private readonly bool $active
    ) {
        Assert::notEmpty($this->name);
        Assert::email($this->email);
        Assert::positiveInteger($this->tariffId);
    }

    public function name(): string
    {
        return $this->name;
    }

    public function email(): string
    {
        return $this->email;
    }

    public function phone(): ?string
    {
        return $this->phone;
    }

    public function tariffId(): int
    {
        return $this->tariffId;
    }

    public function active(): bool
    {
        return $this->active;
    }

    public function toArray(): array
    {
        return [
            'name' => $this->name,
            'email' => $this->email,
            'phone' => $this->phone,
            'tariff_id' => $this->tariffId,
            'active' => $this->active,
        ];
    }

    public static function fromArray(array $data): static
    {
        return new static(
            (string) $data['name'],
            (string) $data['email'],
            $data['phone'] ?? null,
            (int) $data['tariff_id'],
            (bool) $data['active']
        );
    }
}

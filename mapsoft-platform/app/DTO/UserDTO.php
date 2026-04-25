<?php

namespace App\DTO;

use Carbon\CarbonImmutable;
use Carbon\CarbonInterface;
use Webmozart\Assert\Assert;

final class UserDTO
{
    public function __construct(
        private readonly int $id,
        private readonly string $uuid,
        private readonly string $name,
        private readonly string $email,
        private readonly ?string $phone,
        private readonly int $tariffId,
        private readonly int $roleId,
        private readonly bool $active,
        private readonly CarbonInterface $createdAt
    ) {
        Assert::positiveInteger($this->id);
        Assert::uuid($this->uuid);
        Assert::notEmpty($this->name);
        Assert::email($this->email);
        Assert::positiveInteger($this->tariffId);
        Assert::positiveInteger($this->roleId);
    }

    public function id(): int
    {
        return $this->id;
    }

    public function uuid(): string
    {
        return $this->uuid;
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

    public function roleId(): int
    {
        return $this->roleId;
    }

    public function active(): bool
    {
        return $this->active;
    }

    public function createdAt(): CarbonInterface
    {
        return $this->createdAt;
    }

    public function toArray(): array
    {
        return [
            'id' => $this->id,
            'uuid' => $this->uuid,
            'name' => $this->name,
            'email' => $this->email,
            'phone' => $this->phone,
            'tariff_id' => $this->tariffId,
            'role_id' => $this->roleId,
            'active' => $this->active,
            'created_at' => $this->createdAt->toIso8601String(),
        ];
    }

    public static function fromArray(array $data): static
    {
        return new static(
            (int) $data['id'],
            (string) $data['uuid'],
            (string) $data['name'],
            (string) $data['email'],
            $data['phone'] ?? null,
            (int) $data['tariff_id'],
            (int) $data['role_id'],
            (bool) $data['active'],
            CarbonImmutable::parse($data['created_at'])
        );
    }
}

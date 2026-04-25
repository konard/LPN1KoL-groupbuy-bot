<?php

namespace App\DTO;

use Webmozart\Assert\Assert;

final class CreateUserDTO
{
    public function __construct(
        private readonly string $name,
        private readonly string $email,
        private readonly string $password,
        private readonly ?string $phone,
        private readonly int $tariffId,
        private readonly int $roleId
    ) {
        Assert::notEmpty($this->name);
        Assert::email($this->email);
        Assert::minLength($this->password, 8);
        Assert::positiveInteger($this->tariffId);
        Assert::positiveInteger($this->roleId);
    }

    public function name(): string
    {
        return $this->name;
    }

    public function email(): string
    {
        return $this->email;
    }

    public function password(): string
    {
        return $this->password;
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

    public function toArray(): array
    {
        return [
            'name' => $this->name,
            'email' => $this->email,
            'password' => $this->password,
            'phone' => $this->phone,
            'tariff_id' => $this->tariffId,
            'role_id' => $this->roleId,
        ];
    }

    public static function fromArray(array $data): static
    {
        return new static(
            (string) $data['name'],
            (string) $data['email'],
            (string) $data['password'],
            $data['phone'] ?? null,
            (int) $data['tariff_id'],
            (int) $data['role_id']
        );
    }
}

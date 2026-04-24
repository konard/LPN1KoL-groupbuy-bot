<?php

namespace App\DTO;

final class HealthCheckResultDTO
{
    public function __construct(
        private readonly array $services
    ) {
    }

    public function services(): array
    {
        return $this->services;
    }

    public function healthy(): bool
    {
        foreach ($this->services as $service) {
            if (($service['status'] ?? 'down') !== 'ok') {
                return false;
            }
        }

        return true;
    }

    public function toArray(): array
    {
        return [
            'healthy' => $this->healthy(),
            'services' => $this->services,
        ];
    }

    public static function fromArray(array $data): static
    {
        return new static($data['services'] ?? []);
    }
}

<?php

namespace App\Repositories;

use App\Contracts\Repositories\TariffReaderInterface;
use App\DTO\TariffDTO;
use App\Models\Tariff;
use App\Models\User;
use Carbon\CarbonImmutable;
use Illuminate\Support\Collection;

final class EloquentTariffRepository implements TariffReaderInterface
{
    public function __construct(
        private readonly Tariff $model,
        private readonly User $userModel
    ) {
    }

    public function findActive(int $userId): ?TariffDTO
    {
        $user = $this->userModel->newQuery()->with('tariff')->find($userId);
        $tariff = $user?->tariff;

        if (!$tariff instanceof Tariff) {
            return null;
        }

        return $this->toDTO($tariff);
    }

    public function allActive(): Collection
    {
        $today = CarbonImmutable::today()->toDateString();

        return $this->model->newQuery()
            ->whereDate('active_from', '<=', $today)
            ->where(function ($query) use ($today): void {
                $query->whereNull('active_to')->orWhereDate('active_to', '>=', $today);
            })
            ->orderBy('name')
            ->get()
            ->map(fn (Tariff $tariff): TariffDTO => $this->toDTO($tariff));
    }

    private function toDTO(Tariff $tariff): TariffDTO
    {
        return TariffDTO::fromArray([
            'id' => $tariff->id,
            'name' => $tariff->name,
            'price_per_unit' => $tariff->price_per_unit,
            'currency' => $tariff->currency,
            'active_from' => $tariff->active_from,
            'active_to' => $tariff->active_to,
        ]);
    }
}

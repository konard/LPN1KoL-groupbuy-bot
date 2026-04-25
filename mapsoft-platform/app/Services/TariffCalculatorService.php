<?php

namespace App\Services;

use App\Contracts\TariffCalculatorInterface;
use App\DTO\MoneyDTO;
use App\DTO\TariffDTO;

final class TariffCalculatorService implements TariffCalculatorInterface
{
    public function calculate(float $consumption, TariffDTO $tariff): MoneyDTO
    {
        return new MoneyDTO(
            round($consumption * $tariff->pricePerUnit(), 2),
            $tariff->currency()
        );
    }
}

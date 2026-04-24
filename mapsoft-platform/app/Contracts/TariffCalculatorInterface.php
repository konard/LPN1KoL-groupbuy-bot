<?php

namespace App\Contracts;

use App\DTO\MoneyDTO;
use App\DTO\TariffDTO;

interface TariffCalculatorInterface
{
    public function calculate(float $consumption, TariffDTO $tariff): MoneyDTO;
}

<?php

namespace App\Contracts\Repositories;

use App\DTO\TariffDTO;
use Illuminate\Support\Collection;

interface TariffReaderInterface
{
    public function findActive(int $userId): ?TariffDTO;

    public function allActive(): Collection;
}

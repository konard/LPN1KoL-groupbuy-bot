<?php

namespace App\Contracts\Repositories;

use App\DTO\BillDTO;
use App\DTO\BillFilterDTO;
use Illuminate\Support\Collection;

interface BillReaderInterface
{
    public function findByUser(int $userId, BillFilterDTO $filter): Collection;

    public function findByUuid(string $uuid): ?BillDTO;

    public function findOverdue(): Collection;
}

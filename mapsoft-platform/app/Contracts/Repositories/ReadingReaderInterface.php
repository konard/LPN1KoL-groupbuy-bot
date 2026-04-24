<?php

namespace App\Contracts\Repositories;

use App\DTO\ReadingDTO;
use App\DTO\ReadingFilterDTO;
use Carbon\Carbon;
use Illuminate\Support\Collection;

interface ReadingReaderInterface
{
    public function findByUser(int $userId, ReadingFilterDTO $filter): Collection;

    public function findById(int $id): ?ReadingDTO;

    public function sumByUserAndPeriod(int $userId, string $type, Carbon $start, Carbon $end): float;
}

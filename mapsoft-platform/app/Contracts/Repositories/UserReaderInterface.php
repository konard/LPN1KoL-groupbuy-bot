<?php

namespace App\Contracts\Repositories;

use App\DTO\UserDTO;
use Illuminate\Contracts\Pagination\LengthAwarePaginator;
use Illuminate\Support\Collection;

interface UserReaderInterface
{
    public function findById(int $id): ?UserDTO;

    public function findByUuid(string $uuid): ?UserDTO;

    public function paginate(int $perPage): LengthAwarePaginator;

    public function allActive(): Collection;
}

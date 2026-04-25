<?php

namespace App\Contracts\Repositories;

use App\DTO\CreateUserDTO;
use App\DTO\UpdateUserDTO;
use App\DTO\UserDTO;

interface UserWriterInterface
{
    public function create(CreateUserDTO $dto): UserDTO;

    public function update(int $id, UpdateUserDTO $dto): UserDTO;

    public function delete(int $id): void;
}

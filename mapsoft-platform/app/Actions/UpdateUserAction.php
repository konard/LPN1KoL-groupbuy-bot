<?php

namespace App\Actions;

use App\DTO\UpdateUserDTO;
use App\DTO\UserDTO;
use App\Services\UserService;

final class UpdateUserAction
{
    public function __construct(
        private readonly UserService $users
    ) {
    }

    public function execute(int $id, UpdateUserDTO $dto): UserDTO
    {
        return $this->users->update($id, $dto);
    }
}

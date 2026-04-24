<?php

namespace App\Actions;

use App\DTO\CreateUserDTO;
use App\DTO\UserDTO;
use App\Services\UserService;

final class CreateUserAction
{
    public function __construct(
        private readonly UserService $users
    ) {
    }

    public function execute(CreateUserDTO $dto): UserDTO
    {
        return $this->users->create($dto);
    }
}

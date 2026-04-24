<?php

namespace App\Actions;

use App\DTO\UpdateUserDTO;
use App\DTO\UserDTO;
use App\Services\UserService;

final class DeactivateUserAction
{
    public function __construct(
        private readonly UserService $users
    ) {
    }

    public function execute(UserDTO $user): UserDTO
    {
        return $this->users->update($user->id(), new UpdateUserDTO(
            $user->name(),
            $user->email(),
            $user->phone(),
            $user->tariffId(),
            false
        ));
    }
}

<?php

namespace App\Actions;

use App\Services\UserService;

final class DeleteUserAction
{
    public function __construct(
        private readonly UserService $users
    ) {
    }

    public function execute(int $id): void
    {
        $this->users->delete($id);
    }
}

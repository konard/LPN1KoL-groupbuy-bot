<?php

namespace App\Filament\Actions;

use App\Actions\ActivateUserAction as DomainActivateUserAction;
use App\DTO\UserDTO;

final class ActivateUserAction
{
    public function __construct(
        private readonly DomainActivateUserAction $action
    ) {
    }

    public function execute(UserDTO $user): array
    {
        return $this->action->execute($user)->toArray();
    }
}

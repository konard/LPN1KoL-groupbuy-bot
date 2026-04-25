<?php

namespace App\Filament\Actions;

use App\Actions\DeactivateUserAction as DomainDeactivateUserAction;
use App\DTO\UserDTO;

final class DeactivateUserAction
{
    public function __construct(
        private readonly DomainDeactivateUserAction $action
    ) {
    }

    public function execute(UserDTO $user): array
    {
        return $this->action->execute($user)->toArray();
    }
}

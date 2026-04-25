<?php

namespace App\Filament\Actions;

use App\Actions\DeleteUserAction as DomainDeleteUserAction;

final class DeleteUserAction
{
    public function __construct(
        private readonly DomainDeleteUserAction $action
    ) {
    }

    public function execute(int $id): void
    {
        $this->action->execute($id);
    }
}

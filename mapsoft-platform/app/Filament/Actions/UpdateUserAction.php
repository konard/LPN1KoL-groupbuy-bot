<?php

namespace App\Filament\Actions;

use App\Actions\UpdateUserAction as DomainUpdateUserAction;
use App\DTO\UpdateUserDTO;

final class UpdateUserAction
{
    public function __construct(
        private readonly DomainUpdateUserAction $action
    ) {
    }

    public function execute(int $id, array $data): array
    {
        return $this->action->execute($id, UpdateUserDTO::fromArray($data))->toArray();
    }
}

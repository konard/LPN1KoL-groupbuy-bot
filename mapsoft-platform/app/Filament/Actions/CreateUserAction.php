<?php

namespace App\Filament\Actions;

use App\Actions\CreateUserAction as DomainCreateUserAction;
use App\DTO\CreateUserDTO;

final class CreateUserAction
{
    public function __construct(
        private readonly DomainCreateUserAction $action
    ) {
    }

    public function execute(array $data): array
    {
        return $this->action->execute(CreateUserDTO::fromArray($data))->toArray();
    }
}

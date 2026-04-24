<?php

namespace App\Filament\Actions;

use App\Actions\GenerateBillsAction as DomainGenerateBillsAction;

final class GenerateBillsAction
{
    public function __construct(
        private readonly DomainGenerateBillsAction $action
    ) {
    }

    public function execute(string $period): array
    {
        return $this->action->execute($period)
            ->map(fn ($bill): array => $bill->toArray())
            ->all();
    }
}

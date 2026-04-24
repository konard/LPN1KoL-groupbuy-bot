<?php

namespace App\Actions;

use App\Contracts\Repositories\UserReaderInterface;
use App\Services\BillingService;
use Illuminate\Support\Collection;

final class GenerateBillsAction
{
    public function __construct(
        private readonly BillingService $billing,
        private readonly UserReaderInterface $users
    ) {
    }

    public function execute(string $period): Collection
    {
        return $this->users->allActive()
            ->map(fn ($user) => $this->billing->calculateForUser($user->id(), $period));
    }
}

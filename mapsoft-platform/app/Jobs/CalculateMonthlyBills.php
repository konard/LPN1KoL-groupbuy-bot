<?php

namespace App\Jobs;

use App\Contracts\Repositories\UserReaderInterface;
use App\Services\BillingService;
use Illuminate\Contracts\Queue\ShouldQueue;

final class CalculateMonthlyBills implements ShouldQueue
{
    public function __construct(
        private readonly string $period,
        private readonly ?BillingService $billing = null,
        private readonly ?UserReaderInterface $users = null
    ) {
    }

    public function handle(?BillingService $billing = null, ?UserReaderInterface $users = null): void
    {
        $billingService = $this->billing ?? $billing;
        $userReader = $this->users ?? $users;

        if ($billingService === null || $userReader === null) {
            return;
        }

        foreach ($userReader->allActive() as $user) {
            $billingService->calculateForUser($user->id(), $this->period);
        }
    }
}

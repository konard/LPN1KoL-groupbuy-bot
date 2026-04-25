<?php

namespace App\Console\Commands;

use App\Contracts\Repositories\UserReaderInterface;
use App\Services\BillingService;
use Illuminate\Console\Command;

final class CalculateBillsCommand extends Command
{
    protected $signature = 'bills:calculate {period}';

    protected $description = 'Calculate bills for all active users';

    public function __construct(
        private readonly BillingService $billing,
        private readonly UserReaderInterface $users
    ) {
        parent::__construct();
    }

    public function handle(): int
    {
        $period = (string) $this->argument('period');

        foreach ($this->users->allActive() as $user) {
            $this->billing->calculateForUser($user->id(), $period);
        }

        return self::SUCCESS;
    }
}

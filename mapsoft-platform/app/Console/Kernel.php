<?php

namespace App\Console;

use App\Jobs\CalculateMonthlyBills;
use Illuminate\Console\Scheduling\Schedule;
use Illuminate\Foundation\Console\Kernel as ConsoleKernel;

final class Kernel extends ConsoleKernel
{
    protected $commands = [
        \App\Console\Commands\ImportReadingsCommand::class,
        \App\Console\Commands\CalculateBillsCommand::class,
    ];

    protected function schedule(Schedule $schedule): void
    {
        $schedule->job(new CalculateMonthlyBills(now()->subMonth()->format('Y-m')))->monthlyOn(1, '01:00');
    }

    protected function commands(): void
    {
        $this->load(__DIR__ . '/Commands');
        require base_path('routes/console.php');
    }
}

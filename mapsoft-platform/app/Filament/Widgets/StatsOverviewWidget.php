<?php

namespace App\Filament\Widgets;

use App\Contracts\Repositories\BillReaderInterface;
use App\Contracts\Repositories\UserReaderInterface;
use Filament\Widgets\StatsOverviewWidget as BaseWidget;
use Filament\Widgets\StatsOverviewWidget\Stat;

final class StatsOverviewWidget extends BaseWidget
{
    public function __construct(
        private readonly UserReaderInterface $users,
        private readonly BillReaderInterface $bills
    ) {
    }

    protected function getStats(): array
    {
        return [
            Stat::make('Active Users', (string) $this->users->allActive()->count()),
            Stat::make('Overdue Bills', (string) $this->bills->findOverdue()->count()),
        ];
    }
}

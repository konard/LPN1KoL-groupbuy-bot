<?php

namespace App\Providers;

use App\Contracts\BillGeneratorInterface;
use App\Contracts\TariffCalculatorInterface;
use App\Services\BillGeneratorService;
use App\Services\TariffCalculatorService;
use Illuminate\Support\ServiceProvider;

final class AppServiceProvider extends ServiceProvider
{
    public function register(): void
    {
        $this->app->bind(TariffCalculatorInterface::class, TariffCalculatorService::class);
        $this->app->bind(BillGeneratorInterface::class, BillGeneratorService::class);
    }
}

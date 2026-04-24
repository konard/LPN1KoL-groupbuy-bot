<?php

namespace App\Providers;

use App\Contracts\Repositories\BillReaderInterface;
use App\Contracts\Repositories\BillWriterInterface;
use App\Contracts\Repositories\NotificationLogWriterInterface;
use App\Contracts\Repositories\ReadingReaderInterface;
use App\Contracts\Repositories\ReadingWriterInterface;
use App\Contracts\Repositories\TariffReaderInterface;
use App\Contracts\Repositories\UserReaderInterface;
use App\Contracts\Repositories\UserWriterInterface;
use App\Repositories\EloquentBillRepository;
use App\Repositories\EloquentNotificationLogRepository;
use App\Repositories\EloquentReadingRepository;
use App\Repositories\EloquentTariffRepository;
use App\Repositories\EloquentUserRepository;
use Illuminate\Support\ServiceProvider;

final class RepositoryServiceProvider extends ServiceProvider
{
    public function register(): void
    {
        $this->app->bind(UserReaderInterface::class, EloquentUserRepository::class);
        $this->app->bind(UserWriterInterface::class, EloquentUserRepository::class);
        $this->app->bind(ReadingReaderInterface::class, EloquentReadingRepository::class);
        $this->app->bind(ReadingWriterInterface::class, EloquentReadingRepository::class);
        $this->app->bind(BillReaderInterface::class, EloquentBillRepository::class);
        $this->app->bind(BillWriterInterface::class, EloquentBillRepository::class);
        $this->app->bind(TariffReaderInterface::class, EloquentTariffRepository::class);
        $this->app->bind(NotificationLogWriterInterface::class, EloquentNotificationLogRepository::class);
    }
}

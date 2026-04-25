<?php

namespace App\Jobs;

use App\Contracts\Repositories\BillReaderInterface;
use App\DTO\NotificationDTO;
use App\Enums\NotificationChannel;
use App\Enums\NotificationType;
use App\Services\NotificationDispatchService;
use Illuminate\Contracts\Queue\ShouldQueue;

final class SendOverdueNotification implements ShouldQueue
{
    public function __construct(
        private readonly ?BillReaderInterface $bills = null,
        private readonly ?NotificationDispatchService $notifications = null
    ) {
    }

    public function handle(?BillReaderInterface $bills = null, ?NotificationDispatchService $notifications = null): void
    {
        $billReader = $this->bills ?? $bills;
        $dispatcher = $this->notifications ?? $notifications;

        if ($billReader === null || $dispatcher === null) {
            return;
        }

        foreach ($billReader->findOverdue() as $bill) {
            $dispatcher->dispatch(new NotificationDTO(
                0,
                $bill->userId(),
                NotificationType::BillOverdue,
                NotificationChannel::Email,
                $bill->toArray()
            ));
        }
    }
}

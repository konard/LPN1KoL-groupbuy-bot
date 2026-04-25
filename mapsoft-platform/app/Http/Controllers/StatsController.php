<?php

namespace App\Http\Controllers;

use App\Contracts\Repositories\BillReaderInterface;
use App\Contracts\Repositories\ReadingReaderInterface;
use App\DTO\BillFilterDTO;
use App\DTO\ReadingFilterDTO;
use App\Enums\BillStatus;
use App\Http\Resources\StatsResource;
use Carbon\CarbonImmutable;
use Illuminate\Http\Request;
use Illuminate\Routing\Controller as BaseController;

final class StatsController extends BaseController
{
    public function __construct(
        private readonly ReadingReaderInterface $readings,
        private readonly BillReaderInterface $bills
    ) {
    }

    public function monthly(Request $request): StatsResource
    {
        $userId = (int) ($request->integer('user_id') ?: $request->user()?->id ?: 1);
        $start = CarbonImmutable::now()->startOfMonth();
        $end = CarbonImmutable::now()->endOfMonth();
        $readings = $this->readings->findByUser($userId, new ReadingFilterDTO($userId, null, $start, $end, null, 500));
        $bills = $this->bills->findByUser($userId, new BillFilterDTO($userId, BillStatus::Pending, null, null, 100));

        return new StatsResource([
            'consumption' => $readings->sum(fn ($reading): float => $reading->value()),
            'openBills' => $bills->count(),
            'balanceDue' => $bills->sum(fn ($bill): float => $bill->amount()),
        ]);
    }
}

<?php

namespace App\Http\Controllers;

use App\Contracts\Repositories\BillReaderInterface;
use App\DTO\BillFilterDTO;
use App\Enums\BillStatus;
use App\Http\Resources\BillResource;
use Carbon\CarbonImmutable;
use Illuminate\Http\Request;
use Illuminate\Http\Resources\Json\AnonymousResourceCollection;
use Illuminate\Routing\Controller as BaseController;

final class BillController extends BaseController
{
    public function __construct(
        private readonly BillReaderInterface $bills
    ) {
    }

    public function index(Request $request): AnonymousResourceCollection
    {
        $userId = (int) ($request->integer('user_id') ?: $request->user()?->id ?: 1);
        $filter = new BillFilterDTO(
            $userId,
            $request->filled('status') ? BillStatus::from((string) $request->query('status')) : null,
            $request->filled('date_from') ? CarbonImmutable::parse($request->query('date_from')) : null,
            $request->filled('date_to') ? CarbonImmutable::parse($request->query('date_to')) : null,
            (int) ($request->integer('per_page') ?: 50)
        );

        return BillResource::collection($this->bills->findByUser($userId, $filter));
    }

    public function show(string $uuid): BillResource
    {
        return new BillResource($this->bills->findByUuid($uuid));
    }
}

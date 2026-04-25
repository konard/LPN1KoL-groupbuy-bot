<?php

namespace App\Http\Controllers;

use App\Contracts\Repositories\ReadingReaderInterface;
use App\DTO\CreateReadingDTO;
use App\DTO\ReadingFilterDTO;
use App\Enums\ReadingType;
use App\Http\Requests\HistoryReadingRequest;
use App\Http\Requests\StoreReadingRequest;
use App\Http\Resources\ReadingResource;
use App\Services\ReadingPipelineService;
use Carbon\CarbonImmutable;
use Illuminate\Http\Resources\Json\AnonymousResourceCollection;
use Illuminate\Routing\Controller as BaseController;

final class ReadingController extends BaseController
{
    public function __construct(
        private readonly ReadingPipelineService $pipeline,
        private readonly ReadingReaderInterface $readings
    ) {
    }

    public function store(StoreReadingRequest $request): ReadingResource
    {
        $data = $request->validated();
        $userId = (int) ($data['user_id'] ?? $request->user()?->id ?? 1);
        $reading = $this->pipeline->process(new CreateReadingDTO(
            $userId,
            ReadingType::from((string) $data['type']),
            (float) $data['value'],
            CarbonImmutable::parse($data['period_start']),
            CarbonImmutable::parse($data['period_end']),
            (string) $data['idempotency_key']
        ));

        return new ReadingResource($reading);
    }

    public function history(HistoryReadingRequest $request): AnonymousResourceCollection
    {
        $data = $request->validated();
        $userId = (int) ($data['user_id'] ?? $request->user()?->id ?? 1);
        $filter = new ReadingFilterDTO(
            $userId,
            isset($data['type']) ? ReadingType::from((string) $data['type']) : null,
            isset($data['date_from']) ? CarbonImmutable::parse($data['date_from']) : null,
            isset($data['date_to']) ? CarbonImmutable::parse($data['date_to']) : null,
            $data['cursor'] ?? null,
            (int) ($data['limit'] ?? 50)
        );

        return ReadingResource::collection($this->readings->findByUser($userId, $filter));
    }
}

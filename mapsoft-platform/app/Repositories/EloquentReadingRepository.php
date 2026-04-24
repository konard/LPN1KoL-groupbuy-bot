<?php

namespace App\Repositories;

use App\Contracts\Repositories\ReadingReaderInterface;
use App\Contracts\Repositories\ReadingWriterInterface;
use App\DTO\CreateReadingDTO;
use App\DTO\ReadingDTO;
use App\DTO\ReadingFilterDTO;
use App\Exceptions\IdempotencyViolationException;
use App\Models\Reading;
use Carbon\Carbon;
use Carbon\CarbonImmutable;
use Illuminate\Database\QueryException;
use Illuminate\Support\Collection;

final class EloquentReadingRepository implements ReadingReaderInterface, ReadingWriterInterface
{
    public function __construct(
        private readonly Reading $model
    ) {
    }

    public function findByUser(int $userId, ReadingFilterDTO $filter): Collection
    {
        $query = $this->model->newQuery()
            ->where('user_id', $userId)
            ->orderByDesc('period_start')
            ->orderByDesc('id');

        if ($filter->type() !== null) {
            $query->where('type', $filter->type()->value);
        }

        if ($filter->dateFrom() !== null) {
            $query->whereDate('period_start', '>=', $filter->dateFrom()->toDateString());
        }

        if ($filter->dateTo() !== null) {
            $query->whereDate('period_end', '<=', $filter->dateTo()->toDateString());
        }

        if ($filter->cursor() !== null) {
            $query->where('id', '<', (int) $filter->cursor());
        }

        return $query->limit($filter->limit())
            ->get()
            ->map(fn (Reading $reading): ReadingDTO => $this->toDTO($reading));
    }

    public function findById(int $id): ?ReadingDTO
    {
        $reading = $this->model->newQuery()->find($id);

        return $reading instanceof Reading ? $this->toDTO($reading) : null;
    }

    public function sumByUserAndPeriod(int $userId, string $type, Carbon $start, Carbon $end): float
    {
        return (float) $this->model->newQuery()
            ->where('user_id', $userId)
            ->where('type', $type)
            ->whereDate('period_start', '>=', $start)
            ->whereDate('period_end', '<=', $end)
            ->sum('value');
    }

    public function create(CreateReadingDTO $dto): ReadingDTO
    {
        try {
            $reading = $this->model->newQuery()->create([
                'user_id' => $dto->userId(),
                'type' => $dto->type()->value,
                'value' => $dto->value(),
                'period_start' => $dto->periodStart()->toDateString(),
                'period_end' => $dto->periodEnd()->toDateString(),
                'submitted_at' => CarbonImmutable::now(),
                'idempotency_key' => $dto->idempotencyKey(),
            ]);
        } catch (QueryException $exception) {
            throw new IdempotencyViolationException('Reading with this idempotency key already exists', 0, $exception);
        }

        return $this->toDTO($reading);
    }

    private function toDTO(Reading $reading): ReadingDTO
    {
        return ReadingDTO::fromArray([
            'id' => $reading->id,
            'user_id' => $reading->user_id,
            'type' => $reading->type,
            'value' => $reading->value,
            'period_start' => $reading->period_start,
            'period_end' => $reading->period_end,
            'submitted_at' => $reading->submitted_at,
        ]);
    }
}

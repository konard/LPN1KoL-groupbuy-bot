<?php

namespace App\Pipelines\Stages;

use App\Contracts\ReadingPipelineStageInterface;
use App\DTO\ReadingDTO;
use Closure;

final class NormalizeReadingStage implements ReadingPipelineStageInterface
{
    public function handle(ReadingDTO $dto, Closure $next): ReadingDTO
    {
        $normalized = new ReadingDTO(
            $dto->id(),
            $dto->userId(),
            $dto->type(),
            round($dto->value(), 3),
            $dto->periodStart()->startOfDay(),
            $dto->periodEnd()->endOfDay(),
            $dto->submittedAt()
        );

        return $next($normalized);
    }
}

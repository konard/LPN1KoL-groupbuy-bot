<?php

namespace App\Pipelines\Stages;

use App\Contracts\ReadingPipelineStageInterface;
use App\DTO\ReadingDTO;
use Closure;

final class EnrichReadingStage implements ReadingPipelineStageInterface
{
    public function handle(ReadingDTO $dto, Closure $next): ReadingDTO
    {
        return $next($dto);
    }
}

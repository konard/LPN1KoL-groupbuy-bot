<?php

namespace App\Pipelines\Stages;

use App\Contracts\ReadingPipelineStageInterface;
use App\DTO\ReadingDTO;
use App\Exceptions\ReadingValidationException;
use Closure;

final class ValidateReadingStage implements ReadingPipelineStageInterface
{
    public function handle(ReadingDTO $dto, Closure $next): ReadingDTO
    {
        if ($dto->value() < 0) {
            throw new ReadingValidationException('Reading value must be zero or greater');
        }

        if ($dto->periodStart()->greaterThan($dto->periodEnd())) {
            throw new ReadingValidationException('Reading period is invalid');
        }

        return $next($dto);
    }
}

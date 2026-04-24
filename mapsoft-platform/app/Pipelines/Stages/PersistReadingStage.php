<?php

namespace App\Pipelines\Stages;

use App\Contracts\ReadingPipelineStageInterface;
use App\Contracts\Repositories\ReadingWriterInterface;
use App\DTO\CreateReadingDTO;
use App\DTO\ReadingDTO;
use Closure;

final class PersistReadingStage implements ReadingPipelineStageInterface
{
    public function __construct(
        private readonly ReadingWriterInterface $readings
    ) {
    }

    public function handle(ReadingDTO $dto, Closure $next): ReadingDTO
    {
        $persisted = $this->readings->create(new CreateReadingDTO(
            $dto->userId(),
            $dto->type(),
            $dto->value(),
            $dto->periodStart(),
            $dto->periodEnd(),
            hash('sha256', implode(':', [
                $dto->userId(),
                $dto->type()->value,
                $dto->value(),
                $dto->periodStart()->toIso8601String(),
                $dto->periodEnd()->toIso8601String(),
            ]))
        ));

        return $next($persisted);
    }
}

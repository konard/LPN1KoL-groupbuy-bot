<?php

namespace App\Services;

use App\Contracts\ReadingPipelineStageInterface;
use App\DTO\CreateReadingDTO;
use App\DTO\ReadingDTO;
use Carbon\CarbonImmutable;
use Closure;

final class ReadingPipelineService
{
    public function __construct(
        private readonly array $stages
    ) {
    }

    public function process(CreateReadingDTO $dto): ReadingDTO
    {
        $reading = new ReadingDTO(
            0,
            $dto->userId(),
            $dto->type(),
            $dto->value(),
            $dto->periodStart(),
            $dto->periodEnd(),
            CarbonImmutable::now()
        );

        $pipeline = array_reduce(
            array_reverse($this->stages),
            fn (Closure $next, ReadingPipelineStageInterface $stage): Closure => fn (ReadingDTO $reading): ReadingDTO => $stage->handle($reading, $next),
            fn (ReadingDTO $reading): ReadingDTO => $reading
        );

        return $pipeline($reading);
    }
}

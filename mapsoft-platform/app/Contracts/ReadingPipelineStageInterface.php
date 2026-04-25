<?php

namespace App\Contracts;

use App\DTO\ReadingDTO;
use Closure;

interface ReadingPipelineStageInterface
{
    public function handle(ReadingDTO $dto, Closure $next): ReadingDTO;
}

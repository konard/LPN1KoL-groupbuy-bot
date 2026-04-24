<?php

namespace App\Contracts\Repositories;

use App\DTO\CreateReadingDTO;
use App\DTO\ReadingDTO;

interface ReadingWriterInterface
{
    public function create(CreateReadingDTO $dto): ReadingDTO;
}

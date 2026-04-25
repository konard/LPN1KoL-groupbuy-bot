<?php

namespace App\Contracts;

use App\DTO\BillDTO;

interface BillGeneratorInterface
{
    public function generate(int $userId, string $period): BillDTO;
}

<?php

namespace App\Contracts\Repositories;

use App\DTO\BillDTO;
use App\DTO\CreateBillDTO;
use Carbon\Carbon;

interface BillWriterInterface
{
    public function create(CreateBillDTO $dto): BillDTO;

    public function markAsPaid(int $id, Carbon $paidAt): void;
}

<?php

namespace App\Http\Resources;

use App\DTO\BillDTO;
use Illuminate\Http\Request;
use Illuminate\Http\Resources\Json\JsonResource;

final class BillResource extends JsonResource
{
    public function toArray(Request $request): array
    {
        $bill = $this->resource;

        if ($bill instanceof BillDTO) {
            return $bill->toArray();
        }

        return parent::toArray($request);
    }
}

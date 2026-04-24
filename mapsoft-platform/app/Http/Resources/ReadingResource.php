<?php

namespace App\Http\Resources;

use App\DTO\ReadingDTO;
use Illuminate\Http\Request;
use Illuminate\Http\Resources\Json\JsonResource;

final class ReadingResource extends JsonResource
{
    public function toArray(Request $request): array
    {
        $reading = $this->resource;

        if ($reading instanceof ReadingDTO) {
            return $reading->toArray();
        }

        return parent::toArray($request);
    }
}

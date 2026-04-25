<?php

namespace App\Http\Resources;

use App\DTO\TariffDTO;
use Illuminate\Http\Request;
use Illuminate\Http\Resources\Json\JsonResource;

final class TariffResource extends JsonResource
{
    public function toArray(Request $request): array
    {
        $tariff = $this->resource;

        if ($tariff instanceof TariffDTO) {
            return $tariff->toArray();
        }

        return parent::toArray($request);
    }
}

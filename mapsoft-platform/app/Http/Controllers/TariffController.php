<?php

namespace App\Http\Controllers;

use App\Contracts\Repositories\TariffReaderInterface;
use App\Http\Resources\TariffResource;
use Illuminate\Http\Resources\Json\AnonymousResourceCollection;
use Illuminate\Routing\Controller as BaseController;

final class TariffController extends BaseController
{
    public function __construct(
        private readonly TariffReaderInterface $tariffs
    ) {
    }

    public function index(): AnonymousResourceCollection
    {
        return TariffResource::collection($this->tariffs->allActive());
    }
}

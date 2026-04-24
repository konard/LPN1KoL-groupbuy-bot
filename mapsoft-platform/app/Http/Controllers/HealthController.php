<?php

namespace App\Http\Controllers;

use App\Services\HealthCheckService;
use Illuminate\Http\JsonResponse;
use Illuminate\Routing\Controller as BaseController;

final class HealthController extends BaseController
{
    public function __construct(
        private readonly HealthCheckService $health
    ) {
    }

    public function show(): JsonResponse
    {
        $result = $this->health->check();

        return new JsonResponse([
            'data' => $result->toArray(),
        ], $result->healthy() ? 200 : 503);
    }
}

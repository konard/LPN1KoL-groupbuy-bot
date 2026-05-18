<?php

namespace App\Http\Controllers;

use App\Models\ExternalApiRecord;
use Illuminate\Http\JsonResponse;

class ApiRecordController extends Controller
{
    public function index(): JsonResponse
    {
        $records = ExternalApiRecord::query()
            ->latest('fetched_at')
            ->limit(100)
            ->get([
                'id',
                'source',
                'external_id',
                'title',
                'body',
                'fetched_at',
            ]);

        return response()->json($records);
    }
}

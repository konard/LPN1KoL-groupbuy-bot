<?php

namespace App\Http\Controllers;

use App\Models\Visit;
use Illuminate\Http\JsonResponse;
use Illuminate\Http\Request;

class VisitorController extends Controller
{
    public function store(Request $request): JsonResponse
    {
        $data = $request->validate([
            'visitor_id' => ['required', 'string', 'max:100'],
            'ip' => ['nullable', 'string', 'max:45'],
            'city' => ['nullable', 'string', 'max:120'],
            'device' => ['required', 'string', 'max:40'],
            'user_agent' => ['nullable', 'string', 'max:1000'],
            'page_url' => ['nullable', 'string', 'max:2000'],
            'referrer' => ['nullable', 'string', 'max:2000'],
            'visited_at' => ['nullable', 'date'],
        ]);

        Visit::create([
            'visitor_id' => $data['visitor_id'],
            'ip' => $data['ip'] ?? $request->ip(),
            'city' => $data['city'] ?? null,
            'device' => $data['device'],
            'user_agent' => $data['user_agent'] ?? $request->userAgent(),
            'page_url' => $data['page_url'] ?? null,
            'referrer' => $data['referrer'] ?? null,
            'visited_at' => $data['visited_at'] ?? now(),
        ]);

        return response()->json(['status' => 'ok'], 201)->withHeaders([
            'Access-Control-Allow-Origin' => '*',
            'Access-Control-Allow-Headers' => 'Content-Type',
            'Access-Control-Allow-Methods' => 'POST, OPTIONS',
        ]);
    }
}

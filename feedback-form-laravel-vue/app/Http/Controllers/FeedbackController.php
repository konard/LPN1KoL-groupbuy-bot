<?php

namespace App\Http\Controllers;

use App\Services\Feedback\FeedbackStorageFactory;
use Illuminate\Http\JsonResponse;
use Illuminate\Http\Request;

class FeedbackController extends Controller
{
    public function store(Request $request, FeedbackStorageFactory $factory): JsonResponse
    {
        $feedback = $request->validate([
            'name' => ['required', 'string', 'max:255'],
            'message' => ['required', 'string', 'max:5000'],
        ]);

        $driver = config('feedback.storage', 'database');
        $factory->make($driver)->save($feedback);

        return response()->json([
            'data' => $feedback,
            'saved' => true,
        ], 201);
    }
}

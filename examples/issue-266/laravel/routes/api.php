<?php

use App\Http\Controllers\ApiRecordController;
use App\Http\Controllers\VisitorController;
use Illuminate\Support\Facades\Route;

Route::get('/api-records', [ApiRecordController::class, 'index']);
Route::post('/visits', [VisitorController::class, 'store']);
Route::options('/visits', function () {
    return response('', 204)->withHeaders([
        'Access-Control-Allow-Origin' => '*',
        'Access-Control-Allow-Headers' => 'Content-Type',
        'Access-Control-Allow-Methods' => 'POST, OPTIONS',
    ]);
});

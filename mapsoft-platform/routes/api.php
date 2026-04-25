<?php

use App\Http\Controllers\BillController;
use App\Http\Controllers\HealthController;
use App\Http\Controllers\ReadingController;
use App\Http\Controllers\StatsController;
use App\Http\Controllers\TariffController;
use Illuminate\Support\Facades\Route;

Route::prefix('v1')->middleware('throttle:30,1')->group(function (): void {
    Route::post('/readings', [ReadingController::class, 'store']);
    Route::get('/readings/history', [ReadingController::class, 'history']);
    Route::get('/bills', [BillController::class, 'index']);
    Route::get('/bills/{uuid}', [BillController::class, 'show']);
    Route::get('/stats/monthly', [StatsController::class, 'monthly']);
    Route::get('/tariffs', [TariffController::class, 'index']);
    Route::get('/health', [HealthController::class, 'show']);
});

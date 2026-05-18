<?php

use App\Http\Controllers\StatsController;
use App\Http\Middleware\StatsAuth;
use Illuminate\Support\Facades\Route;

Route::redirect('/', '/stats/login');
Route::get('/stats/login', [StatsController::class, 'loginForm'])->name('stats.login');
Route::post('/stats/login', [StatsController::class, 'login']);
Route::post('/stats/logout', [StatsController::class, 'logout'])->name('stats.logout');
Route::get('/stats', [StatsController::class, 'index'])->middleware(StatsAuth::class)->name('stats.index');

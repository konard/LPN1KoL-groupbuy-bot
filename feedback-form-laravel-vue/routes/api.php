<?php

use App\Http\Controllers\FeedbackController;
use Illuminate\Support\Facades\Route;

Route::post('/feedback', [FeedbackController::class, 'store']);

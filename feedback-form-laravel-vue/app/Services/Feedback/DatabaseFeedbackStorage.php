<?php

namespace App\Services\Feedback;

use Illuminate\Support\Facades\Log;

class DatabaseFeedbackStorage implements FeedbackStorageInterface
{
    public function save(array $feedback): void
    {
        Log::info('Feedback saved to database storage', $feedback);
    }
}

<?php

namespace App\Services\Feedback;

use Illuminate\Support\Facades\Log;

class EmailFeedbackStorage implements FeedbackStorageInterface
{
    public function save(array $feedback): void
    {
        Log::info('Feedback sent to email storage', $feedback);
    }
}

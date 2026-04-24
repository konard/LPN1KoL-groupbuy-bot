<?php

namespace App\Services\Feedback;

interface FeedbackStorageInterface
{
    public function save(array $feedback): void;
}

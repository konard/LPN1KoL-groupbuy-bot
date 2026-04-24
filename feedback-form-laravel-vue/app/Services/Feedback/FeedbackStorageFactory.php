<?php

namespace App\Services\Feedback;

use InvalidArgumentException;

class FeedbackStorageFactory
{
    public function make(string $driver): FeedbackStorageInterface
    {
        switch ($driver) {
            case 'database':
                return new DatabaseFeedbackStorage();
            case 'email':
                return new EmailFeedbackStorage();
            default:
                throw new InvalidArgumentException("Unsupported feedback storage driver: {$driver}");
        }
    }
}

<?php

namespace App\Models;

use Illuminate\Database\Eloquent\Model;
use Illuminate\Database\Eloquent\Relations\BelongsTo;

final class Notification extends Model
{
    protected $fillable = [
        'user_id',
        'type',
        'channel',
        'status',
        'payload_json',
    ];

    protected $casts = [
        'payload_json' => 'array',
    ];

    public function user(): BelongsTo
    {
        return $this->belongsTo(User::class);
    }
}

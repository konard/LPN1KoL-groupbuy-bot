<?php

namespace App\Models;

use Illuminate\Database\Eloquent\Model;
use Illuminate\Database\Eloquent\Relations\BelongsTo;
use Illuminate\Database\Eloquent\Relations\HasOne;

final class Reading extends Model
{
    protected $fillable = [
        'user_id',
        'type',
        'value',
        'period_start',
        'period_end',
        'submitted_at',
        'idempotency_key',
    ];

    protected $casts = [
        'value' => 'float',
        'period_start' => 'date',
        'period_end' => 'date',
        'submitted_at' => 'datetime',
    ];

    public function user(): BelongsTo
    {
        return $this->belongsTo(User::class);
    }

    public function billItem(): HasOne
    {
        return $this->hasOne(BillItem::class);
    }
}

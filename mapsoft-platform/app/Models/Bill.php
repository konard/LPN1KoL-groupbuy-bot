<?php

namespace App\Models;

use Illuminate\Database\Eloquent\Model;
use Illuminate\Database\Eloquent\Relations\BelongsTo;
use Illuminate\Database\Eloquent\Relations\HasMany;

final class Bill extends Model
{
    protected $fillable = [
        'uuid',
        'user_id',
        'amount',
        'status',
        'billing_period',
        'due_date',
        'paid_at',
    ];

    protected $casts = [
        'amount' => 'float',
        'due_date' => 'date',
        'paid_at' => 'datetime',
    ];

    public function user(): BelongsTo
    {
        return $this->belongsTo(User::class);
    }

    public function items(): HasMany
    {
        return $this->hasMany(BillItem::class);
    }
}

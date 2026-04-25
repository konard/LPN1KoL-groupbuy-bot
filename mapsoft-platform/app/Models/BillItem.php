<?php

namespace App\Models;

use Illuminate\Database\Eloquent\Model;
use Illuminate\Database\Eloquent\Relations\BelongsTo;

final class BillItem extends Model
{
    public $timestamps = false;

    protected $fillable = [
        'bill_id',
        'reading_id',
        'consumption',
        'price_per_unit',
        'subtotal',
    ];

    protected $casts = [
        'consumption' => 'float',
        'price_per_unit' => 'float',
        'subtotal' => 'float',
    ];

    public function bill(): BelongsTo
    {
        return $this->belongsTo(Bill::class);
    }

    public function reading(): BelongsTo
    {
        return $this->belongsTo(Reading::class);
    }
}

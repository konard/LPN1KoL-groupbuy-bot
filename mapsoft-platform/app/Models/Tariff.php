<?php

namespace App\Models;

use Illuminate\Database\Eloquent\Model;
use Illuminate\Database\Eloquent\Relations\HasMany;

final class Tariff extends Model
{
    protected $fillable = [
        'name',
        'price_per_unit',
        'currency',
        'active_from',
        'active_to',
    ];

    protected $casts = [
        'price_per_unit' => 'float',
        'active_from' => 'date',
        'active_to' => 'date',
    ];

    public function users(): HasMany
    {
        return $this->hasMany(User::class);
    }
}

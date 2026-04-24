<?php

namespace App\Models;

use Illuminate\Database\Eloquent\Model;
use Illuminate\Database\Eloquent\Relations\BelongsTo;
use Illuminate\Database\Eloquent\Relations\HasMany;

final class User extends Model
{
    protected $fillable = [
        'uuid',
        'name',
        'email',
        'phone',
        'password_hash',
        'tariff_id',
        'role_id',
        'active',
    ];

    protected $casts = [
        'active' => 'boolean',
    ];

    public function role(): BelongsTo
    {
        return $this->belongsTo(Role::class);
    }

    public function tariff(): BelongsTo
    {
        return $this->belongsTo(Tariff::class);
    }

    public function readings(): HasMany
    {
        return $this->hasMany(Reading::class);
    }

    public function bills(): HasMany
    {
        return $this->hasMany(Bill::class);
    }
}

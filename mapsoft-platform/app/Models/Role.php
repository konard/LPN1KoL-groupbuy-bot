<?php

namespace App\Models;

use Illuminate\Database\Eloquent\Model;
use Illuminate\Database\Eloquent\Relations\BelongsToMany;
use Illuminate\Database\Eloquent\Relations\HasMany;

final class Role extends Model
{
    public $timestamps = false;

    protected $fillable = [
        'slug',
        'name',
    ];

    public function permissions(): BelongsToMany
    {
        return $this->belongsToMany(PermissionModel::class, 'role_permission', 'role_id', 'permission_id');
    }

    public function users(): HasMany
    {
        return $this->hasMany(User::class);
    }
}

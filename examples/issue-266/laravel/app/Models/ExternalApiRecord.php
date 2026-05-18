<?php

namespace App\Models;

use Illuminate\Database\Eloquent\Model;

class ExternalApiRecord extends Model
{
    protected $fillable = [
        'source',
        'external_id',
        'title',
        'body',
        'fetched_at',
    ];

    protected $casts = [
        'body' => 'array',
        'fetched_at' => 'datetime',
    ];
}

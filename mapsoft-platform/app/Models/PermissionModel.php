<?php

namespace App\Models;

use Illuminate\Database\Eloquent\Model;

final class PermissionModel extends Model
{
    protected $table = 'permissions';

    public $timestamps = false;

    protected $fillable = [
        'slug',
        'name',
    ];
}

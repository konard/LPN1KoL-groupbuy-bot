<?php

namespace Database\Seeders;

use App\Enums\Currency;
use App\Enums\Permission;
use Illuminate\Database\Seeder;
use Illuminate\Support\Facades\DB;

final class DatabaseSeeder extends Seeder
{
    public function run(): void
    {
        $roleId = DB::table('roles')->insertGetId([
            'slug' => 'admin',
            'name' => 'Administrator',
        ]);

        foreach (Permission::cases() as $permission) {
            $permissionId = DB::table('permissions')->insertGetId([
                'slug' => $permission->value,
                'name' => ucfirst(str_replace('_', ' ', $permission->value)),
            ]);
            DB::table('role_permission')->insert([
                'role_id' => $roleId,
                'permission_id' => $permissionId,
            ]);
        }

        DB::table('tariffs')->insert([
            'name' => 'Default',
            'price_per_unit' => 0.2500,
            'currency' => Currency::USD->value,
            'active_from' => now()->startOfYear()->toDateString(),
            'active_to' => null,
            'created_at' => now(),
            'updated_at' => now(),
        ]);
    }
}

<?php

namespace App\Policies;

use App\Enums\Permission;
use App\Models\User;

final class TariffPolicy
{
    public function viewAny(User $user): bool
    {
        return $this->hasPermission($user, Permission::ManageTariffs);
    }

    public function update(User $user): bool
    {
        return $this->hasPermission($user, Permission::ManageTariffs);
    }

    private function hasPermission(User $user, Permission $permission): bool
    {
        return $user->role?->permissions?->contains('slug', $permission->value) ?? false;
    }
}

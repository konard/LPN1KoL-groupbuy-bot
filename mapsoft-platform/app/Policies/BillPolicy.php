<?php

namespace App\Policies;

use App\Enums\Permission;
use App\Models\User;

final class BillPolicy
{
    public function viewAny(User $user): bool
    {
        return $this->hasPermission($user, Permission::ManageBills);
    }

    public function update(User $user): bool
    {
        return $this->hasPermission($user, Permission::ManageBills);
    }

    private function hasPermission(User $user, Permission $permission): bool
    {
        return $user->role?->permissions?->contains('slug', $permission->value) ?? false;
    }
}

<?php

namespace App\Policies;

use App\Enums\Permission;
use App\Models\User;

final class UserPolicy
{
    public function viewAny(User $user): bool
    {
        return $this->hasPermission($user, Permission::ViewUsers);
    }

    public function create(User $user): bool
    {
        return $this->hasPermission($user, Permission::CreateUsers);
    }

    public function update(User $user): bool
    {
        return $this->hasPermission($user, Permission::EditUsers);
    }

    public function delete(User $user): bool
    {
        return $this->hasPermission($user, Permission::DeleteUsers);
    }

    private function hasPermission(User $user, Permission $permission): bool
    {
        return $user->role?->permissions?->contains('slug', $permission->value) ?? false;
    }
}

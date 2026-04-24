<?php

namespace App\Repositories;

use App\Contracts\Repositories\UserReaderInterface;
use App\Contracts\Repositories\UserWriterInterface;
use App\DTO\CreateUserDTO;
use App\DTO\UpdateUserDTO;
use App\DTO\UserDTO;
use App\Models\User;
use Illuminate\Contracts\Pagination\LengthAwarePaginator;
use Illuminate\Support\Collection;
use Illuminate\Support\Str;

final class EloquentUserRepository implements UserReaderInterface, UserWriterInterface
{
    public function __construct(
        private readonly User $model
    ) {
    }

    public function findById(int $id): ?UserDTO
    {
        $user = $this->model->newQuery()->with(['role', 'tariff'])->find($id);

        return $user instanceof User ? $this->toDTO($user) : null;
    }

    public function findByUuid(string $uuid): ?UserDTO
    {
        $user = $this->model->newQuery()->with(['role', 'tariff'])->where('uuid', $uuid)->first();

        return $user instanceof User ? $this->toDTO($user) : null;
    }

    public function paginate(int $perPage): LengthAwarePaginator
    {
        return $this->model->newQuery()
            ->with(['role', 'tariff'])
            ->orderBy('id')
            ->paginate($perPage)
            ->through(fn (User $user): UserDTO => $this->toDTO($user));
    }

    public function allActive(): Collection
    {
        return $this->model->newQuery()
            ->with(['role', 'tariff'])
            ->where('active', true)
            ->orderBy('id')
            ->get()
            ->map(fn (User $user): UserDTO => $this->toDTO($user));
    }

    public function create(CreateUserDTO $dto): UserDTO
    {
        $user = $this->model->newQuery()->create([
            'uuid' => Str::uuid()->toString(),
            'name' => $dto->name(),
            'email' => $dto->email(),
            'phone' => $dto->phone(),
            'password_hash' => password_hash($dto->password(), PASSWORD_BCRYPT),
            'tariff_id' => $dto->tariffId(),
            'role_id' => $dto->roleId(),
            'active' => true,
        ]);

        return $this->toDTO($user);
    }

    public function update(int $id, UpdateUserDTO $dto): UserDTO
    {
        $user = $this->model->newQuery()->findOrFail($id);
        $user->update([
            'name' => $dto->name(),
            'email' => $dto->email(),
            'phone' => $dto->phone(),
            'tariff_id' => $dto->tariffId(),
            'active' => $dto->active(),
        ]);

        return $this->toDTO($user->refresh());
    }

    public function delete(int $id): void
    {
        $this->model->newQuery()->whereKey($id)->delete();
    }

    private function toDTO(User $user): UserDTO
    {
        return UserDTO::fromArray([
            'id' => $user->id,
            'uuid' => $user->uuid,
            'name' => $user->name,
            'email' => $user->email,
            'phone' => $user->phone,
            'tariff_id' => $user->tariff_id,
            'role_id' => $user->role_id,
            'active' => $user->active,
            'created_at' => $user->created_at,
        ]);
    }
}

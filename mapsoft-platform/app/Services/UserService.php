<?php

namespace App\Services;

use App\Contracts\Infrastructure\CacheInterface;
use App\Contracts\Repositories\UserReaderInterface;
use App\Contracts\Repositories\UserWriterInterface;
use App\DTO\CreateUserDTO;
use App\DTO\UpdateUserDTO;
use App\DTO\UserDTO;
use Illuminate\Contracts\Pagination\LengthAwarePaginator;

final class UserService
{
    public function __construct(
        private readonly UserReaderInterface $reader,
        private readonly UserWriterInterface $writer,
        private readonly CacheInterface $cache
    ) {
    }

    public function create(CreateUserDTO $dto): UserDTO
    {
        $user = $this->writer->create($dto);
        $this->cache->tags(['users'])->flushByTag('users');

        return $user;
    }

    public function update(int $id, UpdateUserDTO $dto): UserDTO
    {
        $user = $this->writer->update($id, $dto);
        $this->cache->forget('users:profile:' . $user->uuid());
        $this->cache->tags(['users'])->flushByTag('users');

        return $user;
    }

    public function delete(int $id): void
    {
        $this->writer->delete($id);
        $this->cache->tags(['users'])->flushByTag('users');
    }

    public function find(int $id): ?UserDTO
    {
        return $this->reader->findById($id);
    }

    public function paginate(int $perPage): LengthAwarePaginator
    {
        return $this->reader->paginate($perPage);
    }
}

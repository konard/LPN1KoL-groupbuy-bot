<?php

namespace App\Infrastructure;

use App\Contracts\Infrastructure\TransactionManagerInterface;
use Illuminate\Database\ConnectionInterface;

final class DatabaseTransactionManager implements TransactionManagerInterface
{
    public function __construct(
        private readonly ConnectionInterface $connection
    ) {
    }

    public function beginTransaction(): void
    {
        $this->connection->beginTransaction();
    }

    public function commit(): void
    {
        $this->connection->commit();
    }

    public function rollBack(): void
    {
        $this->connection->rollBack();
    }
}

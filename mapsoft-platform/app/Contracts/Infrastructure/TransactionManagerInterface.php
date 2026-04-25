<?php

namespace App\Contracts\Infrastructure;

interface TransactionManagerInterface
{
    public function beginTransaction(): void;

    public function commit(): void;

    public function rollBack(): void;
}

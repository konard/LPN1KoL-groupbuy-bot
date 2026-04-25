<?php

namespace App\Contracts\Infrastructure;

interface MessageBrokerInterface
{
    public function publish(string $exchange, string $routingKey, array $payload): void;
}

<?php

namespace App\Infrastructure;

use App\Contracts\Infrastructure\MessageBrokerInterface;
use PhpAmqpLib\Channel\AMQPChannel;
use PhpAmqpLib\Message\AMQPMessage;

final class RabbitMQBroker implements MessageBrokerInterface
{
    public function __construct(
        private readonly AMQPChannel $channel
    ) {
    }

    public function publish(string $exchange, string $routingKey, array $payload): void
    {
        $message = new AMQPMessage(json_encode($payload, JSON_THROW_ON_ERROR), [
            'content_type' => 'application/json',
            'delivery_mode' => AMQPMessage::DELIVERY_MODE_PERSISTENT,
        ]);

        $this->channel->basic_publish($message, $exchange, $routingKey);
    }
}

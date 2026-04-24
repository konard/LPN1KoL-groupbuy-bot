<?php

namespace App\Infrastructure;

use App\Contracts\Infrastructure\HttpClientInterface;
use GuzzleHttp\ClientInterface;

final class HttpGuzzleClient implements HttpClientInterface
{
    public function __construct(
        private readonly ClientInterface $client
    ) {
    }

    public function get(string $url, array $headers): array
    {
        $response = $this->client->request('GET', $url, [
            'headers' => $headers,
        ]);

        return json_decode((string) $response->getBody(), true, 512, JSON_THROW_ON_ERROR);
    }

    public function post(string $url, array $data, array $headers): array
    {
        $response = $this->client->request('POST', $url, [
            'headers' => $headers,
            'json' => $data,
        ]);

        return json_decode((string) $response->getBody(), true, 512, JSON_THROW_ON_ERROR);
    }
}

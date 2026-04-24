<?php

namespace Tests\Feature;

use Tests\TestCase;

final class ReadingApiTest extends TestCase
{
    public function test_store_reading_requires_valid_payload(): void
    {
        $response = $this->postJson('/api/v1/readings', [
            'type' => 'electricity',
            'value' => -1,
            'period_start' => '2026-04-01',
            'period_end' => '2026-04-30',
            'idempotency_key' => 'feature-test',
        ]);

        $response->assertStatus(422);
    }

    public function test_health_endpoint_returns_json_data(): void
    {
        $response = $this->getJson('/api/v1/health');

        $response->assertJsonStructure(['data']);
    }
}

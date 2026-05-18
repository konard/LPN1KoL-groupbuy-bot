<?php

namespace App\Console\Commands;

use App\Models\ExternalApiRecord;
use Illuminate\Console\Command;
use Illuminate\Support\Facades\Http;

class FetchApiRecordCommand extends Command
{
    protected $signature = 'api-records:fetch';

    protected $description = 'Fetch data from a public API and store it in the database';

    public function handle(): int
    {
        $response = Http::acceptJson()
            ->timeout(10)
            ->get(config('services.jokes.endpoint'));

        if (! $response->successful()) {
            $this->error('API request failed with status '.$response->status());

            return self::FAILURE;
        }

        $payload = $response->json();

        ExternalApiRecord::create([
            'source' => 'official-joke-api',
            'external_id' => isset($payload['id']) ? (string) $payload['id'] : null,
            'title' => $payload['setup'] ?? 'Untitled record',
            'body' => $payload,
            'fetched_at' => now(),
        ]);

        $this->info('API record saved');

        return self::SUCCESS;
    }
}

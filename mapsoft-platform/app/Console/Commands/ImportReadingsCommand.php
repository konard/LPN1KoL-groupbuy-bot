<?php

namespace App\Console\Commands;

use App\DTO\CreateReadingDTO;
use App\Services\ReadingPipelineService;
use Carbon\CarbonImmutable;
use Illuminate\Console\Command;

final class ImportReadingsCommand extends Command
{
    protected $signature = 'readings:import {path}';

    protected $description = 'Import readings from CSV';

    public function __construct(
        private readonly ReadingPipelineService $pipeline
    ) {
        parent::__construct();
    }

    public function handle(): int
    {
        $path = (string) $this->argument('path');
        $handle = fopen($path, 'rb');

        if ($handle === false) {
            $this->error('Unable to open CSV file');
            return self::FAILURE;
        }

        $imported = 0;

        while (($row = fgetcsv($handle)) !== false) {
            if (count($row) < 6 || $row[0] === 'user_id') {
                continue;
            }

            $this->pipeline->process(CreateReadingDTO::fromArray([
                'user_id' => $row[0],
                'type' => $row[1],
                'value' => $row[2],
                'period_start' => $row[3],
                'period_end' => $row[4],
                'idempotency_key' => $row[5],
            ]));
            $imported++;
        }

        fclose($handle);
        $this->info((string) $imported);

        return self::SUCCESS;
    }
}

<?php

namespace App\Providers;

use App\Contracts\ReadingPipelineStageInterface;
use App\Pipelines\Stages\EnrichReadingStage;
use App\Pipelines\Stages\NormalizeReadingStage;
use App\Pipelines\Stages\PersistReadingStage;
use App\Pipelines\Stages\ValidateReadingStage;
use App\Services\ReadingPipelineService;
use Illuminate\Support\ServiceProvider;

final class PipelineServiceProvider extends ServiceProvider
{
    public function register(): void
    {
        $stages = [
            ValidateReadingStage::class,
            NormalizeReadingStage::class,
            EnrichReadingStage::class,
            PersistReadingStage::class,
        ];

        foreach ($stages as $stage) {
            $this->app->bind($stage);
        }

        $this->app->tag($stages, ReadingPipelineStageInterface::class);

        $this->app->bind(ReadingPipelineService::class, function ($app): ReadingPipelineService {
            return new ReadingPipelineService(iterator_to_array($app->tagged(ReadingPipelineStageInterface::class)));
        });
    }
}

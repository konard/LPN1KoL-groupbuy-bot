<?php

namespace Tests\Unit;

use App\Contracts\ReadingPipelineStageInterface;
use App\DTO\CreateReadingDTO;
use App\DTO\ReadingDTO;
use App\Enums\ReadingType;
use App\Services\ReadingPipelineService;
use Carbon\CarbonImmutable;
use Closure;
use PHPUnit\Framework\TestCase;

final class ReadingPipelineServiceTest extends TestCase
{
    public function test_pipeline_runs_stages_in_order(): void
    {
        $events = [];
        $service = new ReadingPipelineService([
            new RecordingStage('validate', $events),
            new RecordingStage('persist', $events),
        ]);

        $reading = $service->process(new CreateReadingDTO(
            1,
            ReadingType::Electricity,
            42.5,
            CarbonImmutable::parse('2026-04-01'),
            CarbonImmutable::parse('2026-04-30'),
            'pipeline-test'
        ));

        self::assertSame(['validate', 'persist'], $events);
        self::assertSame(42.5, $reading->value());
    }
}

final class RecordingStage implements ReadingPipelineStageInterface
{
    public function __construct(
        private readonly string $name,
        private array &$events
    ) {
    }

    public function handle(ReadingDTO $dto, Closure $next): ReadingDTO
    {
        $this->events[] = $this->name;

        return $next($dto);
    }
}

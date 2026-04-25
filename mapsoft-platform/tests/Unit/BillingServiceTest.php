<?php

namespace Tests\Unit;

use App\Contracts\BillGeneratorInterface;
use App\Contracts\Infrastructure\TransactionManagerInterface;
use App\Contracts\Repositories\BillWriterInterface;
use App\Contracts\Repositories\ReadingReaderInterface;
use App\Contracts\Repositories\TariffReaderInterface;
use App\Contracts\TariffCalculatorInterface;
use App\DTO\BillDTO;
use App\DTO\BillItemDTO;
use App\DTO\CreateBillDTO;
use App\DTO\MoneyDTO;
use App\DTO\ReadingFilterDTO;
use App\DTO\TariffDTO;
use App\Enums\BillStatus;
use App\Enums\Currency;
use App\Services\BillingService;
use Carbon\Carbon;
use Carbon\CarbonImmutable;
use Illuminate\Support\Collection;
use PHPUnit\Framework\TestCase;

final class BillingServiceTest extends TestCase
{
    public function test_calculates_and_persists_bill_inside_transaction(): void
    {
        $transaction = new FakeTransactionManager();
        $service = new BillingService(
            new FakeReadingReader(),
            new FakeTariffReader(),
            new FakeTariffCalculator(),
            new FakeBillGenerator(),
            $writer = new FakeBillWriter(),
            $transaction
        );

        $bill = $service->calculateForUser(7, '2026-04');

        self::assertSame(125.0, $bill->amount());
        self::assertTrue($writer->created);
        self::assertSame(['begin', 'commit'], $transaction->events);
    }
}

final class FakeTransactionManager implements TransactionManagerInterface
{
    public array $events = [];

    public function beginTransaction(): void
    {
        $this->events[] = 'begin';
    }

    public function commit(): void
    {
        $this->events[] = 'commit';
    }

    public function rollBack(): void
    {
        $this->events[] = 'rollback';
    }
}

final class FakeReadingReader implements ReadingReaderInterface
{
    public function findByUser(int $userId, ReadingFilterDTO $filter): Collection
    {
        return collect();
    }

    public function findById(int $id): ?\App\DTO\ReadingDTO
    {
        return null;
    }

    public function sumByUserAndPeriod(int $userId, string $type, Carbon $start, Carbon $end): float
    {
        return $type === 'electricity' ? 500.0 : 0.0;
    }
}

final class FakeTariffReader implements TariffReaderInterface
{
    public function findActive(int $userId): ?TariffDTO
    {
        return new TariffDTO(1, 'Default', 0.25, Currency::USD, CarbonImmutable::parse('2026-01-01'), null);
    }

    public function allActive(): Collection
    {
        return collect();
    }
}

final class FakeTariffCalculator implements TariffCalculatorInterface
{
    public function calculate(float $consumption, TariffDTO $tariff): MoneyDTO
    {
        return new MoneyDTO($consumption * $tariff->pricePerUnit(), $tariff->currency());
    }
}

final class FakeBillGenerator implements BillGeneratorInterface
{
    public function generate(int $userId, string $period): BillDTO
    {
        return new BillDTO(
            0,
            '11111111-1111-4111-8111-111111111111',
            $userId,
            125.0,
            BillStatus::Pending,
            $period,
            CarbonImmutable::parse('2026-05-15'),
            null,
            [new BillItemDTO(0, 0, 1, 500.0, 0.25, 125.0)]
        );
    }
}

final class FakeBillWriter implements BillWriterInterface
{
    public bool $created = false;

    public function create(CreateBillDTO $dto): BillDTO
    {
        $this->created = true;

        return new BillDTO(
            1,
            '22222222-2222-4222-8222-222222222222',
            $dto->userId(),
            $dto->amount(),
            BillStatus::Pending,
            $dto->billingPeriod(),
            $dto->dueDate(),
            null,
            $dto->items()
        );
    }

    public function markAsPaid(int $id, Carbon $paidAt): void
    {
    }
}

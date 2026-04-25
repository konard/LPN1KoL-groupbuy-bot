<?php

namespace App\Services;

use App\Contracts\BillGeneratorInterface;
use App\Contracts\Infrastructure\TransactionManagerInterface;
use App\Contracts\Repositories\BillWriterInterface;
use App\Contracts\Repositories\ReadingReaderInterface;
use App\Contracts\Repositories\TariffReaderInterface;
use App\Contracts\TariffCalculatorInterface;
use App\DTO\BillDTO;
use App\DTO\CreateBillDTO;
use App\Enums\ReadingType;
use App\Exceptions\InsufficientDataException;
use App\Exceptions\TariffExpiredException;
use Carbon\Carbon;
use Throwable;

final class BillingService
{
    public function __construct(
        private readonly ReadingReaderInterface $readings,
        private readonly TariffReaderInterface $tariffs,
        private readonly TariffCalculatorInterface $calculator,
        private readonly BillGeneratorInterface $generator,
        private readonly BillWriterInterface $bills,
        private readonly TransactionManagerInterface $transaction
    ) {
    }

    public function calculateForUser(int $userId, string $period): BillDTO
    {
        $this->transaction->beginTransaction();

        try {
            $start = Carbon::parse($period . '-01')->startOfMonth();
            $end = Carbon::parse($period . '-01')->endOfMonth();
            $tariff = $this->tariffs->findActive($userId);

            if ($tariff === null) {
                throw new TariffExpiredException('Active tariff not found');
            }

            $consumption = 0.0;

            foreach (ReadingType::cases() as $type) {
                $consumption += $this->readings->sumByUserAndPeriod($userId, $type->value, $start, $end);
            }

            $money = $this->calculator->calculate($consumption, $tariff);
            $draft = $this->generator->generate($userId, $period);

            if ($draft->items() === []) {
                throw new InsufficientDataException('No readings for billing period');
            }

            $bill = $this->bills->create(new CreateBillDTO(
                $userId,
                $money->amount(),
                $period,
                $draft->dueDate(),
                $draft->items()
            ));

            $this->transaction->commit();

            return $bill;
        } catch (Throwable $exception) {
            $this->transaction->rollBack();
            throw $exception;
        }
    }
}

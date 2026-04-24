<?php

namespace App\Services;

use App\Contracts\BillGeneratorInterface;
use App\Contracts\Repositories\ReadingReaderInterface;
use App\Contracts\Repositories\TariffReaderInterface;
use App\Contracts\TariffCalculatorInterface;
use App\DTO\BillDTO;
use App\DTO\BillItemDTO;
use App\DTO\ReadingFilterDTO;
use App\Enums\BillStatus;
use App\Exceptions\TariffExpiredException;
use Carbon\CarbonImmutable;
use Illuminate\Support\Str;

final class BillGeneratorService implements BillGeneratorInterface
{
    public function __construct(
        private readonly ReadingReaderInterface $readings,
        private readonly TariffReaderInterface $tariffs,
        private readonly TariffCalculatorInterface $calculator
    ) {
    }

    public function generate(int $userId, string $period): BillDTO
    {
        $start = CarbonImmutable::parse($period . '-01')->startOfMonth();
        $end = CarbonImmutable::parse($period . '-01')->endOfMonth();
        $tariff = $this->tariffs->findActive($userId);

        if ($tariff === null) {
            throw new TariffExpiredException('Active tariff not found');
        }

        $readings = $this->readings->findByUser($userId, new ReadingFilterDTO(
            $userId,
            null,
            $start,
            $end,
            null,
            500
        ));

        $items = $readings->map(function ($reading) use ($tariff): BillItemDTO {
            $money = $this->calculator->calculate($reading->value(), $tariff);

            return new BillItemDTO(
                0,
                0,
                $reading->id(),
                $reading->value(),
                $tariff->pricePerUnit(),
                $money->amount()
            );
        })->all();

        $amount = array_reduce($items, static fn (float $sum, BillItemDTO $item): float => $sum + $item->subtotal(), 0.0);

        return new BillDTO(
            0,
            Str::uuid()->toString(),
            $userId,
            $amount,
            BillStatus::Pending,
            $period,
            $end->addDays(15),
            null,
            $items
        );
    }
}

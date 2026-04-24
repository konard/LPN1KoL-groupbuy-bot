<?php

namespace App\Repositories;

use App\Contracts\Repositories\BillReaderInterface;
use App\Contracts\Repositories\BillWriterInterface;
use App\DTO\BillDTO;
use App\DTO\BillFilterDTO;
use App\DTO\BillItemDTO;
use App\DTO\CreateBillDTO;
use App\Enums\BillStatus;
use App\Exceptions\BillAlreadyPaidException;
use App\Models\Bill;
use App\Models\BillItem;
use Carbon\Carbon;
use Illuminate\Support\Collection;
use Illuminate\Support\Str;

final class EloquentBillRepository implements BillReaderInterface, BillWriterInterface
{
    public function __construct(
        private readonly Bill $model,
        private readonly BillItem $itemModel
    ) {
    }

    public function findByUser(int $userId, BillFilterDTO $filter): Collection
    {
        $query = $this->model->newQuery()
            ->with('items')
            ->where('user_id', $userId)
            ->orderByDesc('due_date');

        if ($filter->status() !== null) {
            $query->where('status', $filter->status()->value);
        }

        if ($filter->dateFrom() !== null) {
            $query->whereDate('due_date', '>=', $filter->dateFrom()->toDateString());
        }

        if ($filter->dateTo() !== null) {
            $query->whereDate('due_date', '<=', $filter->dateTo()->toDateString());
        }

        return $query->limit($filter->perPage())
            ->get()
            ->map(fn (Bill $bill): BillDTO => $this->toDTO($bill));
    }

    public function findByUuid(string $uuid): ?BillDTO
    {
        $bill = $this->model->newQuery()->with('items')->where('uuid', $uuid)->first();

        return $bill instanceof Bill ? $this->toDTO($bill) : null;
    }

    public function findOverdue(): Collection
    {
        return $this->model->newQuery()
            ->with('items')
            ->where('status', BillStatus::Pending->value)
            ->whereDate('due_date', '<', Carbon::today())
            ->get()
            ->map(fn (Bill $bill): BillDTO => $this->toDTO($bill));
    }

    public function create(CreateBillDTO $dto): BillDTO
    {
        $bill = $this->model->newQuery()->create([
            'uuid' => Str::uuid()->toString(),
            'user_id' => $dto->userId(),
            'amount' => $dto->amount(),
            'status' => BillStatus::Pending->value,
            'billing_period' => $dto->billingPeriod(),
            'due_date' => $dto->dueDate()->toDateString(),
        ]);

        foreach ($dto->items() as $item) {
            $this->itemModel->newQuery()->create([
                'bill_id' => $bill->id,
                'reading_id' => $item->readingId(),
                'consumption' => $item->consumption(),
                'price_per_unit' => $item->pricePerUnit(),
                'subtotal' => $item->subtotal(),
            ]);
        }

        return $this->toDTO($bill->load('items'));
    }

    public function markAsPaid(int $id, Carbon $paidAt): void
    {
        $bill = $this->model->newQuery()->findOrFail($id);

        if ($bill->status === BillStatus::Paid->value) {
            throw new BillAlreadyPaidException('Bill is already paid');
        }

        $bill->update([
            'status' => BillStatus::Paid->value,
            'paid_at' => $paidAt,
        ]);
    }

    private function toDTO(Bill $bill): BillDTO
    {
        return BillDTO::fromArray([
            'id' => $bill->id,
            'uuid' => $bill->uuid,
            'user_id' => $bill->user_id,
            'amount' => $bill->amount,
            'status' => $bill->status,
            'billing_period' => $bill->billing_period,
            'due_date' => $bill->due_date,
            'paid_at' => $bill->paid_at,
            'items' => $bill->items->map(
                fn (BillItem $item): array => (new BillItemDTO(
                    $item->id,
                    $item->bill_id,
                    $item->reading_id,
                    $item->consumption,
                    $item->price_per_unit,
                    $item->subtotal
                ))->toArray()
            )->all(),
        ]);
    }
}

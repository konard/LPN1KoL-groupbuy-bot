<?php

namespace App\Http\Requests;

use App\Enums\ReadingType;
use Illuminate\Foundation\Http\FormRequest;
use Illuminate\Validation\Rule;

final class StoreReadingRequest extends FormRequest
{
    public function authorize(): bool
    {
        return true;
    }

    public function rules(): array
    {
        return [
            'user_id' => ['sometimes', 'integer', 'min:1'],
            'type' => ['required', Rule::enum(ReadingType::class)],
            'value' => ['required', 'numeric', 'min:0'],
            'period_start' => ['required', 'date'],
            'period_end' => ['required', 'date', 'after_or_equal:period_start'],
            'idempotency_key' => ['required', 'string', 'max:128'],
        ];
    }
}

<?php

namespace App\Http\Requests;

use App\Enums\ReadingType;
use Illuminate\Foundation\Http\FormRequest;
use Illuminate\Validation\Rule;

final class HistoryReadingRequest extends FormRequest
{
    public function authorize(): bool
    {
        return true;
    }

    public function rules(): array
    {
        return [
            'user_id' => ['sometimes', 'integer', 'min:1'],
            'type' => ['sometimes', Rule::enum(ReadingType::class)],
            'date_from' => ['sometimes', 'date'],
            'date_to' => ['sometimes', 'date', 'after_or_equal:date_from'],
            'cursor' => ['sometimes', 'string'],
            'limit' => ['sometimes', 'integer', 'min:1', 'max:500'],
        ];
    }
}

<?php

namespace App\Filament\Resources;

use App\Enums\ReadingType;
use App\Models\Reading;
use Filament\Forms\Components\DatePicker;
use Filament\Forms\Components\Select;
use Filament\Forms\Components\TextInput;
use Filament\Forms\Form;
use Filament\Resources\Resource;
use Filament\Tables\Columns\TextColumn;
use Filament\Tables\Filters\SelectFilter;
use Filament\Tables\Table;

final class ReadingResource extends Resource
{
    protected static ?string $model = Reading::class;

    public static function form(Form $form): Form
    {
        return $form->schema([
            Select::make('user_id')->relationship('user', 'email')->required(),
            Select::make('type')->options(self::typeOptions())->required(),
            TextInput::make('value')->numeric()->required(),
            DatePicker::make('period_start')->required(),
            DatePicker::make('period_end')->required(),
        ]);
    }

    public static function table(Table $table): Table
    {
        return $table
            ->columns([
                TextColumn::make('user.email')->label('User')->searchable(),
                TextColumn::make('type')->sortable(),
                TextColumn::make('value')->sortable(),
                TextColumn::make('period_start')->date()->sortable(),
                TextColumn::make('period_end')->date()->sortable(),
                TextColumn::make('submitted_at')->dateTime()->sortable(),
            ])
            ->filters([
                SelectFilter::make('type')->options(self::typeOptions()),
            ]);
    }

    private static function typeOptions(): array
    {
        $options = [];

        foreach (ReadingType::cases() as $type) {
            $options[$type->value] = ucfirst($type->value);
        }

        return $options;
    }
}

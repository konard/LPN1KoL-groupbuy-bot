<?php

namespace App\Filament\Resources;

use App\Enums\Currency;
use App\Models\Tariff;
use Filament\Forms\Components\DatePicker;
use Filament\Forms\Components\Select;
use Filament\Forms\Components\TextInput;
use Filament\Forms\Form;
use Filament\Resources\Resource;
use Filament\Tables\Actions\DeleteAction;
use Filament\Tables\Actions\EditAction;
use Filament\Tables\Columns\TextColumn;
use Filament\Tables\Table;

final class TariffResource extends Resource
{
    protected static ?string $model = Tariff::class;

    public static function form(Form $form): Form
    {
        return $form->schema([
            TextInput::make('name')->required()->maxLength(255),
            TextInput::make('price_per_unit')->numeric()->required(),
            Select::make('currency')->options(self::currencyOptions())->required(),
            DatePicker::make('active_from')->required(),
            DatePicker::make('active_to'),
        ]);
    }

    public static function table(Table $table): Table
    {
        return $table
            ->columns([
                TextColumn::make('name')->searchable()->sortable(),
                TextColumn::make('price_per_unit')->money('USD')->sortable(),
                TextColumn::make('currency')->sortable(),
                TextColumn::make('active_from')->date()->sortable(),
                TextColumn::make('active_to')->date()->sortable(),
            ])
            ->actions([
                EditAction::make(),
                DeleteAction::make(),
            ]);
    }

    private static function currencyOptions(): array
    {
        $options = [];

        foreach (Currency::cases() as $currency) {
            $options[$currency->value] = $currency->value;
        }

        return $options;
    }
}

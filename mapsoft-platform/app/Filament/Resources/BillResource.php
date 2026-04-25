<?php

namespace App\Filament\Resources;

use App\Enums\BillStatus;
use App\Models\Bill;
use Filament\Forms\Components\DatePicker;
use Filament\Forms\Components\Select;
use Filament\Forms\Components\TextInput;
use Filament\Forms\Form;
use Filament\Resources\Resource;
use Filament\Tables\Actions\EditAction;
use Filament\Tables\Columns\TextColumn;
use Filament\Tables\Filters\SelectFilter;
use Filament\Tables\Table;

final class BillResource extends Resource
{
    protected static ?string $model = Bill::class;

    public static function form(Form $form): Form
    {
        return $form->schema([
            Select::make('user_id')->relationship('user', 'email')->required(),
            TextInput::make('amount')->numeric()->required(),
            Select::make('status')->options(self::statusOptions())->required(),
            TextInput::make('billing_period')->required()->maxLength(7),
            DatePicker::make('due_date')->required(),
        ]);
    }

    public static function table(Table $table): Table
    {
        return $table
            ->columns([
                TextColumn::make('uuid')->searchable(),
                TextColumn::make('user.email')->label('User')->searchable(),
                TextColumn::make('amount')->money('USD')->sortable(),
                TextColumn::make('status')->sortable(),
                TextColumn::make('billing_period')->sortable(),
                TextColumn::make('due_date')->date()->sortable(),
            ])
            ->filters([
                SelectFilter::make('status')->options(self::statusOptions()),
            ])
            ->actions([
                EditAction::make(),
            ]);
    }

    private static function statusOptions(): array
    {
        $options = [];

        foreach (BillStatus::cases() as $status) {
            $options[$status->value] = ucfirst($status->value);
        }

        return $options;
    }
}

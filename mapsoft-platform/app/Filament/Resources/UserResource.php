<?php

namespace App\Filament\Resources;

use App\Models\User;
use Filament\Forms\Components\Select;
use Filament\Forms\Components\TextInput;
use Filament\Forms\Form;
use Filament\Resources\Resource;
use Filament\Tables\Actions\DeleteAction;
use Filament\Tables\Actions\EditAction;
use Filament\Tables\Columns\IconColumn;
use Filament\Tables\Columns\TextColumn;
use Filament\Tables\Filters\SelectFilter;
use Filament\Tables\Table;

final class UserResource extends Resource
{
    protected static ?string $model = User::class;

    public static function form(Form $form): Form
    {
        return $form->schema([
            TextInput::make('name')->required()->maxLength(255),
            TextInput::make('email')->email()->required()->maxLength(255),
            TextInput::make('phone')->tel()->maxLength(40),
            Select::make('role_id')->relationship('role', 'name')->required(),
            Select::make('tariff_id')->relationship('tariff', 'name')->required(),
            Select::make('active')->options([1 => 'Active', 0 => 'Inactive'])->required(),
        ]);
    }

    public static function table(Table $table): Table
    {
        return $table
            ->columns([
                TextColumn::make('name')->searchable()->sortable(),
                TextColumn::make('email')->searchable(),
                TextColumn::make('role.name')->label('Role')->sortable(),
                TextColumn::make('tariff.name')->label('Tariff')->sortable(),
                IconColumn::make('active')->boolean(),
                TextColumn::make('readings_max_submitted_at')->label('Last Reading')->dateTime(),
                TextColumn::make('bills_sum_amount')->label('Total Debt')->money('USD'),
            ])
            ->filters([
                SelectFilter::make('active')->options([1 => 'Active', 0 => 'Inactive']),
                SelectFilter::make('role')->relationship('role', 'name'),
                SelectFilter::make('tariff')->relationship('tariff', 'name'),
            ])
            ->actions([
                EditAction::make(),
                DeleteAction::make(),
            ]);
    }
}

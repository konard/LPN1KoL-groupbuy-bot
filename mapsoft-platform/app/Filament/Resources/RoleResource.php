<?php

namespace App\Filament\Resources;

use App\Models\Role;
use Filament\Forms\Components\TextInput;
use Filament\Forms\Form;
use Filament\Resources\Resource;
use Filament\Tables\Actions\DeleteAction;
use Filament\Tables\Actions\EditAction;
use Filament\Tables\Columns\TextColumn;
use Filament\Tables\Table;

final class RoleResource extends Resource
{
    protected static ?string $model = Role::class;

    public static function form(Form $form): Form
    {
        return $form->schema([
            TextInput::make('slug')->required()->maxLength(80),
            TextInput::make('name')->required()->maxLength(255),
        ]);
    }

    public static function table(Table $table): Table
    {
        return $table
            ->columns([
                TextColumn::make('slug')->searchable()->sortable(),
                TextColumn::make('name')->searchable()->sortable(),
            ])
            ->actions([
                EditAction::make(),
                DeleteAction::make(),
            ]);
    }
}

<?php

use Illuminate\Database\Migrations\Migration;
use Illuminate\Database\Schema\Blueprint;
use Illuminate\Support\Facades\Schema;

return new class extends Migration {
    public function up(): void
    {
        Schema::create('tariffs', function (Blueprint $table): void {
            $table->id();
            $table->string('name');
            $table->decimal('price_per_unit', 12, 4);
            $table->string('currency', 3);
            $table->date('active_from');
            $table->date('active_to')->nullable();
            $table->timestamps();
            $table->index(['active_from', 'active_to']);
        });
    }

    public function down(): void
    {
        Schema::dropIfExists('tariffs');
    }
};

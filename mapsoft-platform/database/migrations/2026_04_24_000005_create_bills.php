<?php

use Illuminate\Database\Migrations\Migration;
use Illuminate\Database\Schema\Blueprint;
use Illuminate\Support\Facades\Schema;

return new class extends Migration {
    public function up(): void
    {
        Schema::create('bills', function (Blueprint $table): void {
            $table->id();
            $table->uuid('uuid')->unique();
            $table->foreignId('user_id')->constrained()->cascadeOnDelete();
            $table->decimal('amount', 14, 2);
            $table->string('status');
            $table->string('billing_period', 7);
            $table->date('due_date')->index();
            $table->timestamp('paid_at')->nullable();
            $table->timestamps();
            $table->index(['user_id', 'status']);
        });

        Schema::create('bill_items', function (Blueprint $table): void {
            $table->id();
            $table->foreignId('bill_id')->constrained()->cascadeOnDelete();
            $table->unsignedBigInteger('reading_id');
            $table->decimal('consumption', 18, 6);
            $table->decimal('price_per_unit', 12, 4);
            $table->decimal('subtotal', 14, 2);
        });
    }

    public function down(): void
    {
        Schema::dropIfExists('bill_items');
        Schema::dropIfExists('bills');
    }
};

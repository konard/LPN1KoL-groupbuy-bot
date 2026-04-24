<?php

use Illuminate\Database\Migrations\Migration;
use Illuminate\Database\Schema\Blueprint;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Facades\Schema;

return new class extends Migration {
    public function up(): void
    {
        Schema::create('users', function (Blueprint $table): void {
            $table->id();
            $table->uuid('uuid')->unique();
            $table->string('name');
            $table->string('email')->index();
            $table->string('phone')->nullable();
            $table->string('password_hash');
            $table->foreignId('tariff_id')->constrained()->restrictOnDelete();
            $table->foreignId('role_id')->constrained()->restrictOnDelete();
            $table->boolean('active')->default(true);
            $table->timestamps();
            $table->index(['tariff_id', 'active']);
        });

        DB::statement("CREATE INDEX users_name_search_idx ON users USING gin (to_tsvector('simple', name))");
    }

    public function down(): void
    {
        Schema::dropIfExists('users');
    }
};

<?php

use Illuminate\Database\Migrations\Migration;
use Illuminate\Database\Schema\Blueprint;
use Illuminate\Support\Facades\Schema;

return new class extends Migration
{
    public function up(): void
    {
        Schema::create('external_api_records', function (Blueprint $table): void {
            $table->id();
            $table->string('source');
            $table->string('external_id')->nullable()->index();
            $table->string('title');
            $table->json('body');
            $table->timestamp('fetched_at')->index();
            $table->timestamps();
        });
    }

    public function down(): void
    {
        Schema::dropIfExists('external_api_records');
    }
};

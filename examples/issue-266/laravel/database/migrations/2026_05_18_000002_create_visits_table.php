<?php

use Illuminate\Database\Migrations\Migration;
use Illuminate\Database\Schema\Blueprint;
use Illuminate\Support\Facades\Schema;

return new class extends Migration
{
    public function up(): void
    {
        Schema::create('visits', function (Blueprint $table): void {
            $table->id();
            $table->string('visitor_id', 100)->index();
            $table->string('ip', 45)->nullable();
            $table->string('city', 120)->nullable()->index();
            $table->string('device', 40);
            $table->string('user_agent', 1000)->nullable();
            $table->string('page_url', 2000)->nullable();
            $table->string('referrer', 2000)->nullable();
            $table->timestamp('visited_at')->index();
            $table->timestamps();
        });
    }

    public function down(): void
    {
        Schema::dropIfExists('visits');
    }
};

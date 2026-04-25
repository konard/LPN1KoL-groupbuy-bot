<?php

use Illuminate\Database\Migrations\Migration;
use Illuminate\Support\Facades\DB;

return new class extends Migration {
    public function up(): void
    {
        DB::statement("
            CREATE TABLE readings (
                id BIGSERIAL,
                user_id BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                type VARCHAR(32) NOT NULL,
                value NUMERIC(18, 6) NOT NULL,
                period_start DATE NOT NULL,
                period_end DATE NOT NULL,
                submitted_at TIMESTAMP WITHOUT TIME ZONE NOT NULL,
                idempotency_key VARCHAR(128) NOT NULL,
                created_at TIMESTAMP WITHOUT TIME ZONE,
                updated_at TIMESTAMP WITHOUT TIME ZONE,
                PRIMARY KEY (id, period_start),
                UNIQUE (user_id, idempotency_key, period_start)
            ) PARTITION BY RANGE (period_start)
        ");

        DB::statement("CREATE TABLE readings_2026 PARTITION OF readings FOR VALUES FROM ('2026-01-01') TO ('2027-01-01')");
        DB::statement("CREATE TABLE readings_2027 PARTITION OF readings FOR VALUES FROM ('2027-01-01') TO ('2028-01-01')");
        DB::statement("CREATE INDEX readings_user_id_idx ON readings (user_id)");
        DB::statement("CREATE INDEX readings_user_type_period_idx ON readings (user_id, type, period_start)");
        DB::statement("CREATE INDEX readings_electricity_idx ON readings (user_id, period_start) WHERE type = 'electricity'");
    }

    public function down(): void
    {
        DB::statement('DROP TABLE IF EXISTS readings CASCADE');
    }
};

<?php

use Illuminate\Support\Facades\Artisan;

Artisan::command('mapsoft:ping', function (): void {
    $this->info('pong');
});

<?php

return [
    'name' => env('APP_NAME', 'MapsoftPlatform'),
    'env' => env('APP_ENV', 'production'),
    'debug' => (bool) env('APP_DEBUG', false),
    'url' => env('APP_URL', 'http://localhost'),
    'key' => env('APP_KEY'),
    'providers' => [
        App\Providers\AppServiceProvider::class,
        App\Providers\RepositoryServiceProvider::class,
        App\Providers\InfrastructureServiceProvider::class,
        App\Providers\PipelineServiceProvider::class,
        App\Providers\NotificationServiceProvider::class,
        App\Providers\RouteServiceProvider::class,
    ],
];

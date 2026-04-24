# Mapsoft Platform

Laravel 9 and Vue 3 platform for collecting utility meter readings, calculating bills, notifying users, and operating an administrative panel.

## Stack

- Laravel 9, PHP 8.1, PostgreSQL, Redis, RabbitMQ
- Filament v3 resources for operational administration
- Vue 3, Vite, Chart.js, Axios client dashboard
- Docker Compose services for app, nginx, worker, scheduler, PostgreSQL, Redis, RabbitMQ

## Local Setup

```bash
composer install
npm install
cp .env.example .env
php artisan key:generate
php artisan migrate
npm run dev
```

## Verification

```bash
composer test
composer analyse
npm run build
docker compose config
```

# Feedback Form Laravel Vue

Minimal feedback form application for issue 87.

## What Is Included

- Laravel API endpoint: `POST /api/feedback`
- Storage factory with `database` and `email` drivers
- Vue 3 SPA with Vuex and Vue Router
- Form page with `name` and `message` fields
- List page that renders only feedback saved in Vuex

## Local Setup

```bash
composer install
npm install
cp .env.example .env
php artisan key:generate
php artisan serve
npm run dev
```

The frontend keeps submitted feedback in Vuex only. Reloading the page clears the list, as requested.

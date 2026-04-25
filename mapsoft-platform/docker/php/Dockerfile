FROM php:8.1-fpm-alpine

WORKDIR /var/www/html

RUN apk add --no-cache git unzip postgresql-dev libzip-dev rabbitmq-c-dev \
    && docker-php-ext-install pdo pdo_pgsql zip opcache

COPY --from=composer:2 /usr/bin/composer /usr/bin/composer

COPY composer.json composer.json
RUN composer install --no-dev --no-interaction --prefer-dist --no-scripts

COPY . .

RUN composer dump-autoload --optimize

CMD ["php-fpm"]

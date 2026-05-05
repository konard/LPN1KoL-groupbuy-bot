# gateway (FastAPI)

FastAPI rewrite of the API gateway, per issue
[#178](https://github.com/LPN1KoL/groupbuy-bot/issues/178).

The gateway listens on port **3000** and forwards `/api/v1/{service}/{path}` to
the matching upstream microservice URL.

## Endpoints

| Method | Path                              | Description                                              |
|--------|-----------------------------------|----------------------------------------------------------|
| GET    | `/health`                         | Liveness probe.                                          |
| ANY    | `/api/v1/{service_name}/{path}`   | Authenticated proxy to the resolved upstream service.    |

`service_name` is one of `auth`, `purchases`, `payments`, `chat`, `notifications`,
`analytics`, `search`, `reputation`. Each name maps to the corresponding
`*_SERVICE_URL` environment variable.

## Authentication

Requests must include `Authorization: Bearer <jwt>` validated against
`JWT_SECRET` (HS256). Public paths exempt from auth:

- `POST /api/v1/auth/login`
- `POST /api/v1/auth/register`
- `POST /api/v1/auth/refresh`
- `POST /api/v1/auth/forgot-password`
- `POST /api/v1/auth/reset-password`

Decoded `sub` and `role` claims are forwarded as `X-User-Id` and `X-User-Role`
headers.

## Rate limiting

Per-minute fixed-window counter stored in Redis at key `ratelimit:{identity}`,
limited by `RATE_LIMIT_RPM` (default 60). Identity is the JWT `sub` if present,
otherwise the client IP. Returns `429 Too Many Requests` when exceeded.

## Environment variables

| Variable                   | Default                                  |
|----------------------------|------------------------------------------|
| `PORT`                     | `3000`                                   |
| `JWT_SECRET`               | `dev-jwt-secret`                         |
| `JWT_ALGORITHM`            | `HS256`                                  |
| `RATE_LIMIT_RPM`           | `60`                                     |
| `CORS_ORIGINS`             | `*` (comma-separated list)               |
| `REDIS_ADDR`               | `redis:6379`                             |
| `REDIS_PASSWORD`           | _(empty)_                                |
| `REDIS_URL`                | derived from `REDIS_ADDR` and password   |
| `AUTH_SERVICE_URL`         | `http://auth-service:4001`               |
| `PURCHASE_SERVICE_URL`     | `http://purchase-service:4002`           |
| `PAYMENT_SERVICE_URL`      | `http://payment-service:4003`            |
| `CHAT_SERVICE_URL`         | `http://chat-service:4004`               |
| `NOTIFICATION_SERVICE_URL` | `http://notification-service:4005`       |
| `ANALYTICS_SERVICE_URL`    | `http://analytics-service:4006`          |
| `SEARCH_SERVICE_URL`       | `http://search-service:4007`             |
| `REPUTATION_SERVICE_URL`   | `http://reputation-service:4008`         |

## Frontend wiring (issue #178, section 3)

The React container should call the gateway, not the core service directly.
Set this in the frontend environment:

```
API_BASE_URL=http://gateway:3000
```

`CORS_ORIGINS` on the gateway must include the frontend origin
(e.g. `http://localhost:3000` for browser dev, plus `http://frontend-react`
for in-cluster requests).

## Build the image

```bash
docker build -t groupbuy-gateway .
```

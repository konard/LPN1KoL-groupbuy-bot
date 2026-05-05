# core (FastAPI)

FastAPI rewrite of the legacy Rust `core-rust/` service, per issue
[#178](https://github.com/LPN1KoL/groupbuy-bot/issues/178).

## Endpoints

| Method | Path                 | Description                                  |
|--------|----------------------|----------------------------------------------|
| GET    | `/health`            | Liveness probe (used by docker healthcheck). |
| GET    | `/api/products`      | List products (cached in Redis for 30s).     |
| POST   | `/api/products`      | Create a product.                            |
| GET    | `/api/products/{id}` | Fetch a single product.                      |
| PATCH  | `/api/products/{id}` | Partial update.                              |
| DELETE | `/api/products/{id}` | Delete a product.                            |

## Environment variables

| Variable       | Default                                                          | Notes                              |
|----------------|------------------------------------------------------------------|------------------------------------|
| `DATABASE_URL` | `postgresql://postgres:postgres@postgres:5432/groupbuy`          | asyncpg DSN.                       |
| `REDIS_URL`    | `redis://redis:6379/0`                                           | Used for response caching.         |
| `PORT`         | `8000`                                                           | uvicorn bind port.                 |
| `LOG_LEVEL`    | `INFO`                                                           | Replaces the Rust `RUST_LOG` knob. |

## Run locally

```bash
pip install -r requirements.txt
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/groupbuy \
REDIS_URL=redis://localhost:6379/0 \
uvicorn main:app --host 0.0.0.0 --port 8000
```

## Build the image

```bash
docker build -t groupbuy-core .
```

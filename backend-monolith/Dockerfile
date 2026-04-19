##############################################################################
# Multi-stage Dockerfile for backend-monolith
#
# Stages:
#   1. rust-builder  — compiles core-rust/ into a Python extension (.so) via PyO3
#   2. python-builder — installs Python deps and copies the Rust .so
#   3. final          — python:3.12-slim production image
#
# Build context is the repo root so that core/ and core-rust/ are accessible.
# In docker-compose.monolith.yml:
#   build:
#     context: .
#     dockerfile: backend-monolith/Dockerfile
##############################################################################

# ─── Stage 1: Rust builder ───────────────────────────────────────────────────
FROM rust:1.88-slim AS rust-builder

RUN apt-get update && apt-get install -y --no-install-recommends \
    pkg-config \
    libssl-dev \
    libpq-dev \
    python3-dev \
    && rm -rf /var/lib/apt/lists/*

# Install maturin to build PyO3 extensions
RUN pip3 install maturin --break-system-packages 2>/dev/null || \
    (curl https://bootstrap.pypa.io/get-pip.py -o /tmp/get-pip.py && python3 /tmp/get-pip.py && pip3 install maturin)

WORKDIR /build

# Copy core-rust source for PyO3 binding compilation
COPY core-rust/ ./core-rust/

WORKDIR /build/core-rust

# Build the Rust library as a Python extension (produces groupbuy_core.so)
# Uses PyO3 feature flag; falls back to building static lib if no PyO3 bindings present
RUN maturin build --release --out /build/dist 2>/dev/null || \
    (cargo build --release && \
     mkdir -p /build/dist && \
     cp target/release/libgroupbuy*.so /build/dist/groupbuy_core.so 2>/dev/null || \
     echo "No shared library produced, Rust code compiled as binary only")

# ─── Stage 2: Python builder ─────────────────────────────────────────────────
FROM python:3.12-slim AS python-builder

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY backend-monolith/requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

# Copy Rust-built artifacts (wheel or .so)
COPY --from=rust-builder /build/dist/ /build/dist/
RUN find /build/dist -name "*.whl" -exec pip install --no-cache-dir --prefix=/install {} \; || true

# ─── Stage 3: Final slim image ───────────────────────────────────────────────
FROM python:3.12-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy installed Python packages
COPY --from=python-builder /install /usr/local

# Copy Rust .so artifacts (if any)
COPY --from=rust-builder /build/dist/ /tmp/rust-dist/
RUN find /tmp/rust-dist -name "*.so" -exec cp {} /usr/local/lib/python3.12/site-packages/ \; 2>/dev/null || true \
    && rm -rf /tmp/rust-dist

# Copy the Django legacy core (used for admin API and ML analytics utilities)
COPY core/ ./core/

# Copy the monolith application source
COPY backend-monolith/ .

ENV PYTHONPATH=/app:/app/core
ENV PORT=4000

EXPOSE 4000

# Run Alembic migrations then start FastAPI
# NOTE: Socket.IO is mounted as an ASGI app via socket_app; uvicorn must point
# to that wrapper so WebSocket upgrades are handled at the ASGI layer.
CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:socket_app --host 0.0.0.0 --port ${PORT:-4000}"]

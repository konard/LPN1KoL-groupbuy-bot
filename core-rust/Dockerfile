# Build stage
FROM rust:1.88-slim AS builder

RUN apt-get update && apt-get install -y \
    pkg-config \
    libssl-dev \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy dependency files first for caching
COPY Cargo.toml Cargo.lock ./
RUN mkdir src && echo "fn main() {}" > src/main.rs
RUN cargo build --release 2>/dev/null || true
RUN rm -rf src

# Copy full source
COPY . .
# Touch main.rs to ensure it's rebuilt (cached dummy may have newer timestamp)
RUN touch src/main.rs
RUN cargo build --release

# Runtime stage
FROM debian:bookworm-slim

RUN apt-get update && apt-get install -y \
    libpq5 \
    ca-certificates \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY --from=builder /app/target/release/groupbuy-api /app/groupbuy-api
COPY --from=builder /app/migrations /app/migrations

ENV RUST_LOG=info,groupbuy_api=debug
ENV PORT=8000

EXPOSE 8000

CMD ["/app/groupbuy-api"]
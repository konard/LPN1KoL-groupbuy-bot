# Build Rust to WebAssembly
FROM rust:1.88-slim AS builder

RUN apt-get update && apt-get install -y curl && rm -rf /var/lib/apt/lists/*

# Install wasm-pack
RUN curl https://rustwasm.github.io/wasm-pack/installer/init.sh -sSf | sh

WORKDIR /app

# Copy source
COPY wasm-utils/Cargo.toml wasm-utils/Cargo.lock ./
COPY wasm-utils/src ./src

# Build WASM package for web target
RUN wasm-pack build --target web --out-dir /wasm-pkg

# Output stage - minimal image with just the built artifacts
FROM alpine:3.19
COPY --from=builder /wasm-pkg /wasm-pkg
CMD ["echo", "WASM package built successfully. Output in /wasm-pkg/"]

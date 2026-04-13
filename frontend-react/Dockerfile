# Build stage
FROM node:20-alpine AS builder

WORKDIR /app

# Copy package files
COPY package.json package-lock.json ./

# Install dependencies
RUN npm ci

# Copy source code (includes pre-built WASM package in src/wasm-pkg/)
COPY . .

# Build the application with WASM support
RUN npm run build

# Production stage
FROM nginx:alpine

# Install curl for Docker healthcheck
RUN apk add --no-cache curl

# Copy built files to nginx
COPY --from=builder /app/dist /usr/share/nginx/html

# Copy nginx configuration
COPY nginx.conf /etc/nginx/conf.d/default.conf

# Expose port 80
EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]

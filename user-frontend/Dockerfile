FROM node:20-alpine AS builder

WORKDIR /app

COPY package*.json ./
RUN npm ci

COPY . .
RUN npm run build

FROM node:20-alpine

WORKDIR /app

ENV NODE_ENV=production
ENV PORT=3000
# Bind on all interfaces so the Docker healthcheck can reach localhost:3000.
# Docker sets $HOSTNAME to the container ID; Next.js standalone uses $HOSTNAME
# as the bind address and would otherwise only listen on the container's primary IP.
ENV HOSTNAME=0.0.0.0

# Next.js standalone output
COPY --from=builder /app/.next/standalone ./
COPY --from=builder /app/.next/static ./.next/static
COPY --from=builder /app/public ./public

EXPOSE 3000

CMD ["node", "server.js"]

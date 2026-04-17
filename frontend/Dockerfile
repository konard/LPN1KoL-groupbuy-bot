# Build stage
FROM node:20-alpine AS build
WORKDIR /app
COPY package.json .
RUN npm install
COPY . .
ARG VITE_BACKEND_URL=/api
ARG VITE_SOCKET_URL=ws://localhost/socket
ENV VITE_BACKEND_URL=$VITE_BACKEND_URL
ENV VITE_SOCKET_URL=$VITE_SOCKET_URL
RUN npm run build

# Serve stage
FROM nginx:alpine
COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80

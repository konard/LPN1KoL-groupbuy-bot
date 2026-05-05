FROM nginx:alpine

# Copy custom entrypoint and ensure it is executable regardless of host FS
COPY docker-entrypoint.sh /docker-entrypoint-custom.sh
RUN chmod +x /docker-entrypoint-custom.sh

EXPOSE 80 443 8000

ENTRYPOINT ["/docker-entrypoint-custom.sh"]

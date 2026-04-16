FROM alpine:3.20

RUN apk add --no-cache pgbouncer postgresql-client su-exec \
    && (addgroup -S pgbouncer 2>/dev/null || true) \
    && (adduser -S -D -H -h /var/lib/pgbouncer -s /sbin/nologin -G pgbouncer pgbouncer 2>/dev/null || true) \
    && mkdir -p /etc/pgbouncer /var/log/pgbouncer /var/run/pgbouncer \
    && chown -R pgbouncer:pgbouncer /etc/pgbouncer /var/log/pgbouncer /var/run/pgbouncer

COPY docker-entrypoint.sh /usr/local/bin/docker-entrypoint.sh
RUN chmod +x /usr/local/bin/docker-entrypoint.sh

EXPOSE 6432
ENTRYPOINT ["/usr/local/bin/docker-entrypoint.sh"]

# Troubleshooting: `groupbuy-postgres` init failures

This guide covers the recurring class of errors where the postgres container in
any of the `docker-compose*.yml` stacks (most often `docker-compose.python.yml`)
fails on first boot with one or more of the following log lines:

```
groupbuy-postgres | /usr/local/bin/docker-entrypoint.sh: running /docker-entrypoint-initdb.d/init-databases.sh
groupbuy-postgres | /usr/local/bin/docker-entrypoint.sh: /docker-entrypoint-initdb.d/init-databases.sh: /bin/bash^M: bad interpreter: No such file or directory
groupbuy-postgres | /usr/local/bin/docker-entrypoint.sh: /docker-entrypoint-initdb.d/init-databases.sh: /bin/bash: bad interpreter: No such file or directory
groupbuy-postgres | PostgreSQL Database directory appears to contain a database; Skipping initialization
```

Once you see this, every dependent service (`core`, `bot`, `django-admin`, etc.)
will fail with "database does not exist" on startup, because the additional
databases (`auth_db`, `purchase_db`, `payment_db`, `chat_db`, `reputation_db`)
were never created.

## Why it happens

Four independent bugs can produce this log. The repository is hardened against
all four (see `.gitattributes`, the `#!/bin/sh` shebang and executable bit on
`scripts/init-databases.sh`, and the `:ro` mount in every compose file), but if
you cloned the repo on
Windows with `core.autocrlf=true` *before* the `.gitattributes` fix landed, your
working copy may still be in the broken state.

| # | Symptom in logs | Root cause |
|---|---|---|
| 1 | `bad interpreter: /bin/bash^M` | `init-databases.sh` checked out with CRLF (Windows) line endings instead of LF (Unix). |
| 2 | `bad interpreter: /bin/bash` | The script uses `#!/bin/bash`, but `postgres:16-alpine` includes `/bin/sh` and does not install bash. |
| 3 | `psql: ... is a directory` (silent skip) | `init-databases.sh` does not have the user-executable bit, so the postgres entrypoint *sources* it and fails under `set -e`. |
| 4 | `Skipping initialization` | The postgres data volume already exists from a previous failed boot, so the entrypoint never runs init scripts again. |

## Fix (existing clone)

Run all three steps in your repo root:

```bash
# 1. Convert CRLF -> LF for the init script (and any other shell script)
#    Either tool works; pick the one you have.
sed -i 's/\r$//' scripts/init-databases.sh infrastructure/postgres/init-databases.sh
# or:
# dos2unix scripts/init-databases.sh infrastructure/postgres/init-databases.sh

# 2. Make sure the script uses the shell available in postgres:16-alpine.
sed -i '1s|^#!.*|#!/bin/sh|' scripts/init-databases.sh infrastructure/postgres/init-databases.sh

# 3. Restore the executable bit (so postgres-entrypoint runs the script
#    instead of sourcing it).
chmod +x scripts/init-databases.sh infrastructure/postgres/init-databases.sh

# 4. Wipe the half-initialized postgres data volume so the entrypoint
#    actually runs init-databases.sh again.
#    WARNING: this destroys all local postgres data — only do this on
#    a development machine.
docker compose -f docker-compose.python.yml down -v
docker compose -f docker-compose.python.yml up --build -d
```

After step 4 the postgres logs should show the five `CREATE DATABASE` lines and
end with `All databases created successfully.`

To remove only the postgres container and compose-managed postgres volume:

```bash
docker compose -f docker-compose.python.yml stop postgres
docker compose -f docker-compose.python.yml rm -f postgres
docker volume rm groupbuy-bot_postgres_data
docker compose -f docker-compose.python.yml up --build -d
docker logs groupbuy-postgres
```

If the compose project name differs, find the volume name with:

```bash
docker volume ls | grep postgres_data
```

## Verification commands

Run these from the repository root before restarting the stack:

```bash
head -n 1 scripts/init-databases.sh infrastructure/postgres/init-databases.sh
grep -n $'\r' scripts/init-databases.sh infrastructure/postgres/init-databases.sh || true
sh -n scripts/init-databases.sh
sh -n infrastructure/postgres/init-databases.sh
git ls-files -s scripts/init-databases.sh infrastructure/postgres/init-databases.sh
pytest tests/test_issue_139_crlf_and_exec_bits.py tests/test_issue_152_crlf_postgres_init.py -q
```

## Prevention (already in place)

- `.gitattributes` enforces `*.sh text eol=lf` so future clones — including
  on Windows with `core.autocrlf=true` — get LF endings.
- `scripts/init-databases.sh` and `infrastructure/postgres/init-databases.sh`
  use `#!/bin/sh`, which is available in `postgres:16-alpine`.
- `scripts/init-databases.sh` and `infrastructure/postgres/init-databases.sh`
  both have the executable bit committed (mode `0755`).
- Every `docker-compose*.yml` mounts the init script with `:ro` so the postgres
  container cannot accidentally rewrite or chmod it.
- CI (`.github/workflows/ci.yml`) runs `docker compose config --quiet` on every
  compose file (including `docker-compose.python.yml`), greps every shell script
  for `\r`, and runs `tests/test_issue_*_*.py` so any regression in the above
  surfaces on the PR instead of in production logs.

## Alternative: rebuild the image with the script baked in

The default setup bind-mounts `init-databases.sh` from the host. If you would
rather not depend on host file permissions, build a custom postgres image with
the script copied in:

```dockerfile
# infrastructure/postgres/Dockerfile
FROM postgres:16-alpine
COPY init-databases.sh /docker-entrypoint-initdb.d/init-databases.sh
RUN apk add --no-cache dos2unix \
    && dos2unix /docker-entrypoint-initdb.d/init-databases.sh \
    && sed -i '1s|^#!.*|#!/bin/sh|' /docker-entrypoint-initdb.d/init-databases.sh \
    && chmod +x /docker-entrypoint-initdb.d/init-databases.sh
```

Then in your compose file replace `image: postgres:16-alpine` with a `build:`
block and remove the `volumes:` mount of `init-databases.sh`. This eliminates
the CRLF / exec-bit class of bugs entirely at the cost of needing to rebuild
the image when the script changes.

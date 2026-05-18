#!/usr/bin/env bash
# Apply db/schema.sql to the running Postgres container.
# Extensions are already installed via infra/init/01-extensions.sql at container start.
set -euo pipefail

cd "$(dirname "$0")/../.."

docker compose -f infra/docker-compose.yml exec -T db \
  psql -U relocate -d relocate < db/schema.sql

echo "schema applied ✓"

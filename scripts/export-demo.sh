#!/usr/bin/env bash
# Refresh data/demo.sql from the local Docker Postgres (maintainers only).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

if ! docker inspect -f '{{.State.Running}}' trendscout-db 2>/dev/null | grep -qx true; then
  echo "Start Postgres first: docker compose up -d db" >&2
  exit 1
fi

docker exec trendscout-db pg_dump \
  -U trendscout \
  -d trendscout \
  --data-only \
  --no-owner \
  --no-privileges \
  > "$ROOT/data/demo.sql"

echo "Wrote $ROOT/data/demo.sql ($(wc -c < "$ROOT/data/demo.sql") bytes)"

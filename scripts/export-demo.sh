#!/usr/bin/env bash
# Refresh data/demo.sql from local Docker Postgres (maintainers only).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

if ! docker inspect -f '{{.State.Running}}' trendscout-db 2>/dev/null | grep -qx true; then
  echo "Start Postgres first: docker compose up -d db" >&2
  exit 1
fi

python3 "$ROOT/scripts/build_demo_sql.py"
echo "Demo snapshot ready for commit (vectors stripped — works with EMBEDDING_DIM=384)."

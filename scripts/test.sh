#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."

echo "== API =="
(cd services/api && python -m pip install -q -r requirements-dev.txt && python -m pytest -q)

echo "== Webhook receiver =="
(cd services/notify && { [ -d node_modules ] || npm ci --no-audit --no-fund; } && npm test)

echo "== Web =="
(cd apps/web && { [ -d node_modules ] || npm ci --no-audit --no-fund; } && npm run typecheck && npm test && npm run build)

if [ "${E2E:-}" = "1" ]; then
  SKIP_INSTALL=1 ./scripts/e2e.sh
fi

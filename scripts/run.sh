#!/usr/bin/env bash
# PostgreSQL, Redis, API (:8086), worker, webhook receiver (:8090), and the web app (:3006).
set -euo pipefail
cd "$(dirname "$0")/.."
docker compose -f infra/docker-compose.yml up --build "$@"

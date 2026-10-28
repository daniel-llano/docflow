# PostgreSQL, Redis, API (:8086), worker, webhook receiver (:8090), and the web app (:3006).
Set-Location (Join-Path $PSScriptRoot "..")
docker compose -f infra/docker-compose.yml up --build @args

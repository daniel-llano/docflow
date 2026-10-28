param([switch]$E2E)
Set-Location (Join-Path $PSScriptRoot "..")

function Step([string]$Dir, [scriptblock]$Body) {
  Push-Location $Dir
  try { & $Body; if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE } } finally { Pop-Location }
}

Step services/api { python -m pip install -q -r requirements-dev.txt; python -m pytest -q }
Step services/notify { if (-not (Test-Path node_modules)) { npm ci --no-audit --no-fund }; npm test }
Step apps/web { if (-not (Test-Path node_modules)) { npm ci --no-audit --no-fund }; npm run typecheck; npm test; npm run build }

if ($E2E -or $env:E2E -eq "1") {
  & (Join-Path $PSScriptRoot "e2e.ps1") -SkipInstall
  exit $LASTEXITCODE
}

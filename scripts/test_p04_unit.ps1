# P04 unit/API tests in isolated one-off Tenant container, no PostgreSQL changes.
param([string]$ProjectRoot=(Split-Path -Parent $PSScriptRoot))
Set-StrictMode -Version Latest
$ErrorActionPreference='Stop'
Push-Location $ProjectRoot
try {
  & docker compose -f compose.yaml -f compose.p04-unit.yaml build tenant
  if ($LASTEXITCODE -ne 0) { throw 'Tenant build failed' }
  & docker compose -f compose.yaml -f compose.p04-unit.yaml run --rm --no-deps tenant `
    sh -c 'python -m pip install --disable-pip-version-check -q -r /app/requirements-test.txt && python -m pytest tests -q --cov=app.service --cov-report=term-missing --cov-fail-under=80'
  if ($LASTEXITCODE -ne 0) { throw 'P04 Tenant unit/API tests failed' }
  Write-Host 'P04 TENANT UNIT/API OK: service coverage >=80%' -ForegroundColor Green
} finally { Pop-Location }

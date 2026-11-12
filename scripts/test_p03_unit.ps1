# P03 domain / HTTP / messaging unit tests; no live databases.
param([string]$ProjectRoot = (Split-Path -Parent $PSScriptRoot))
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
Push-Location $ProjectRoot
try {
  & docker compose -f compose.yaml -f infra/compose/tests/room-meter-unit.yaml build room metering
  if ($LASTEXITCODE -ne 0) { throw 'Build P03 unit images failed' }
  & docker compose -f compose.yaml -f infra/compose/tests/room-meter-unit.yaml run --rm --no-deps room `
    sh -c 'python -m pip install --disable-pip-version-check -q -r /app/requirements-test.txt && python -m pytest -q tests --cov=app --cov-report=term-missing --cov-fail-under=95'
  if ($LASTEXITCODE -ne 0) { throw 'P03 Room unit tests failed' }
  & docker compose -f compose.yaml -f infra/compose/tests/room-meter-unit.yaml run --rm --no-deps metering `
    sh -c 'python -m pip install --disable-pip-version-check -q -r /app/requirements-test.txt && python -m pytest -q tests --ignore=tests/integration --cov=app.service --cov=app.repository --cov=app.messaging --cov=app.api_internal --cov-report=term-missing --cov-fail-under=90'
  if ($LASTEXITCODE -ne 0) { throw 'P03 Metering unit tests failed' }
  Write-Host 'P03 UNIT OK: Room >=95% and Metering business modules >=90%' -ForegroundColor Green
} finally { Pop-Location }

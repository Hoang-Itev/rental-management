# Fast P02 tests in a disposable Room container; no DB writes.
param([string]$ProjectRoot = (Split-Path -Parent $PSScriptRoot))
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
Push-Location $ProjectRoot
try {
  & docker compose -f compose.yaml -f compose.room-test.yaml build room
  if ($LASTEXITCODE -ne 0) { throw 'Room image build failed' }
  & docker compose -f compose.yaml -f compose.room-test.yaml run --rm --no-deps room `
    sh -c 'python -m pip install --disable-pip-version-check -q -r /app/requirements-test.txt && python -m pytest -q tests --cov=app --cov-report=term-missing --cov-fail-under=95'
  if ($LASTEXITCODE -ne 0) { throw 'Room unit/API tests failed' }
  Write-Host 'ROOM UNIT/API TESTS OK (>=95% coverage)' -ForegroundColor Green
} finally { Pop-Location }

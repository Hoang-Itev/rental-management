# Executes P01 tests inside an ephemeral Auth container, without touching live DB.
param([string]$ProjectRoot = (Split-Path -Parent $PSScriptRoot))
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
Push-Location $ProjectRoot
try {
  & docker compose -f compose.yaml -f infra/compose/tests/auth-unit.yaml build auth
  if ($LASTEXITCODE -ne 0) { throw 'Auth image build failed' }
  & docker compose -f compose.yaml -f infra/compose/tests/auth-unit.yaml run --rm --no-deps auth `
    sh -c 'python -m pip install --disable-pip-version-check -q -r /app/requirements-test.txt && python -m pytest -q tests --cov=app --cov-report=term-missing --cov-fail-under=95'
  if ($LASTEXITCODE -ne 0) { throw 'Auth unit/API tests failed' }
  Write-Host 'AUTH UNIT/API TESTS OK (>=95% coverage)' -ForegroundColor Green
} finally {
  Pop-Location
}

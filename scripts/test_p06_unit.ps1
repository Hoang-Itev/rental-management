# P06 local unit checks. No database or broker required.
param([string]$ProjectRoot=(Split-Path -Parent $PSScriptRoot))
Set-StrictMode -Version Latest
$ErrorActionPreference='Stop'
Push-Location $ProjectRoot
try {
  if (-not (Test-Path '.env')) { throw 'Missing project .env' }
  $files=@('-f','compose.yaml','-f','infra/compose/tests/mqtt-unit.yaml')
  & docker compose @files config --quiet
  if ($LASTEXITCODE -ne 0) { throw 'Invalid P06 unit Compose overlay' }
  & docker compose @files build metering simulator
  if ($LASTEXITCODE -ne 0) { throw 'P06 image build failed' }
  & docker compose @files run --rm --no-deps metering sh -c 'python -m pip install -q --disable-pip-version-check -r /app/requirements-test.txt && python -m pytest -q tests --ignore=tests/integration --cov=app.service --cov-report=term-missing --cov-fail-under=80'
  if ($LASTEXITCODE -ne 0) { throw 'P06 Metering unit tests FAILED' }
  & docker compose @files run --rm --no-deps simulator sh -c 'python -m pip install -q --disable-pip-version-check pytest && python -m pytest -q tests'
  if ($LASTEXITCODE -ne 0) { throw 'P06 Simulator unit tests FAILED' }
  Write-Host 'P06 UNIT OK: Metering >=80%, Simulator tests passed' -ForegroundColor Green
} finally { Pop-Location }

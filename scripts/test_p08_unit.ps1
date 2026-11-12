# P08 Billing calculator unit tests: Docker image only; no DB/RabbitMQ/Nginx.
param([string]$ProjectRoot=(Split-Path -Parent $PSScriptRoot))
Set-StrictMode -Version Latest
$ErrorActionPreference='Stop'
Push-Location $ProjectRoot
try {
  if (-not (Test-Path '.env')) { throw 'Missing project .env (used for Compose interpolation)' }
  $files=@('-f','compose.yaml','-f','compose.p08-unit.yaml')
  & docker compose @files config --quiet
  if ($LASTEXITCODE -ne 0) { throw 'P08 Compose config invalid' }
  & docker compose @files build billing
  if ($LASTEXITCODE -ne 0) { throw 'P08 Billing image build FAILED' }
  & docker compose @files run --rm --no-deps billing sh -c 'python -m pip install -q --disable-pip-version-check -r /app/requirements-test.txt && python -m pytest tests/test_service.py -q --cov=app.calculator --cov-report=term-missing --cov-fail-under=80'
  if ($LASTEXITCODE -ne 0) { throw 'P08 calculator unit tests FAILED' }
  Write-Host 'P08 calculator unit tests PASS (>=80% coverage)' -ForegroundColor Green
} finally { Pop-Location }

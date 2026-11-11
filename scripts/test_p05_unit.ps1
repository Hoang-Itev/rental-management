# Run from ANY directory; ProjectRoot is normally inferred from this script path.
param([string]$ProjectRoot=(Split-Path -Parent $PSScriptRoot))
Set-StrictMode -Version Latest
$ErrorActionPreference='Stop'
Push-Location $ProjectRoot
try {
    $files=@('-f','compose.yaml','-f','compose.p03-unit.yaml','-f','compose.p04-unit.yaml')
    & docker compose @files build room tenant metering
    if ($LASTEXITCODE -ne 0) { throw 'P05 Docker image build failed' }
    & docker compose @files run --rm --no-deps room `
      sh -c 'python -m pip install --disable-pip-version-check -q -r /app/requirements-test.txt && python -m pytest tests -q --cov=app --cov-report=term-missing --cov-fail-under=95'
    if ($LASTEXITCODE -ne 0) { throw 'P05 Room unit/consumer tests failed' }
    & docker compose @files run --rm --no-deps tenant `
      sh -c 'python -m pip install --disable-pip-version-check -q -r /app/requirements-test.txt && python -m pytest tests -q --cov=app.service --cov-report=term-missing --cov-fail-under=80'
    if ($LASTEXITCODE -ne 0) { throw 'P05 Tenant unit/lifecycle tests failed' }
    & docker compose @files run --rm --no-deps metering `
      sh -c 'python -m pip install --disable-pip-version-check -q -r /app/requirements-test.txt && python -m pytest -q tests/test_service.py tests/test_api.py tests/test_messaging.py tests/test_lifecycle.py --cov=app.service --cov-report=term-missing --cov-fail-under=80'
    if ($LASTEXITCODE -ne 0) { throw 'P05 Metering unit/cutoff tests failed' }
    Write-Host 'P05 UNIT OK: Room >=95%, Tenant >=80%, Metering >=80%' -ForegroundColor Green
} finally { Pop-Location }

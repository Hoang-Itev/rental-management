# Disposable REAL PostgreSQL and RabbitMQ. NEVER down -v on rental-management.
param([string]$ProjectRoot=(Split-Path -Parent (Split-Path -Parent $PSScriptRoot)))
Set-StrictMode -Version Latest
$ErrorActionPreference='Stop'
$project='p05test'+([guid]::NewGuid().ToString('N').Substring(0,10))
if ($env:P05_CI_PROJECT_NAME) { $project=$env:P05_CI_PROJECT_NAME }
if (-not ($project.StartsWith('p05test') -or $project.StartsWith('p05ci'))) {
    throw 'Refusing unsafe P05 project name'
}
$env:P05_PROJECT_NAME=$project
$files=@('-p',$project,'-f','compose.yaml', '-f', 'compose.workers.yaml','-f','infra/compose/tests/contract-lifecycle.yaml')
Push-Location $ProjectRoot
try {
    if (-not (Test-Path .env)) { throw 'Missing .env in project directory' }
    Write-Host "P05 DISPOSABLE PROJECT: $project" -ForegroundColor Cyan
    & docker compose @files config --quiet
    if ($LASTEXITCODE -ne 0) { throw 'P05 Compose configuration invalid' }
    & docker compose @files up -d --wait postgres rabbitmq
    if ($LASTEXITCODE -ne 0) { throw 'PostgreSQL/RabbitMQ failed to start' }
    & docker compose @files up -d rabbitmq-init
    if ($LASTEXITCODE -ne 0) { throw 'Rabbit topology init start failed' }
    & docker compose @files wait rabbitmq-init
    if ($LASTEXITCODE -ne 0) { throw 'Rabbit topology init failed' }
    & docker compose @files build room tenant metering
    if ($LASTEXITCODE -ne 0) { throw 'Failed building service images' }
    foreach ($svc in @('room','tenant','metering')) {
      & docker compose @files run --rm --no-deps $svc python -m alembic upgrade head
      if ($LASTEXITCODE -ne 0) { throw "P05 $svc migrations failed" }
    }
    & docker compose @files up -d --wait room tenant metering
    if ($LASTEXITCODE -ne 0) { throw 'HTTP services failed readiness' }
    & docker compose @files up -d room-outbox room-consumer metering-consumer tenant-outbox tenant-scheduler
    if ($LASTEXITCODE -ne 0) { throw 'Lifecycle worker startup failed' }
    & docker compose @files run --rm --no-deps tenant `
      sh -c 'python -m pip install --disable-pip-version-check -q -r /app/requirements-test.txt && python -m pytest -q integration/test_contract_lifecycle.py'
    if ($LASTEXITCODE -ne 0) { throw 'P05 real Room/Tenant/Metering integration failed' }
    Write-Host 'P05 REAL INTEGRATION OK: lifecycle, handover order, stale events, cutoff reasons' -ForegroundColor Green
} catch {
    Write-Host 'P05 FAILED. Collecting disposable container logs:' -ForegroundColor Red
    & docker compose @files ps -a | Out-Host
    & docker compose @files logs --tail=90 room tenant metering room-consumer metering-consumer tenant-outbox tenant-scheduler postgres rabbitmq | Out-Host
    throw
} finally {
    Write-Host "Cleaning ONLY disposable project: $project" -ForegroundColor Yellow
    & docker compose @files down -v --remove-orphans --rmi local | Out-Host
    Remove-Item Env:P05_PROJECT_NAME -ErrorAction SilentlyContinue
    Pop-Location
}

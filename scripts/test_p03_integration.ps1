# P03 full broker integration in random throwaway Compose project.
# NEVER down -v the existing rental-management Docker project.
param([string]$ProjectRoot = (Split-Path -Parent $PSScriptRoot))
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$project = 'p03test' + ([guid]::NewGuid().ToString('N').Substring(0,10))
if ($env:P03_CI_PROJECT_NAME) { $project = $env:P03_CI_PROJECT_NAME }
if (-not $project.StartsWith('p03test') -and -not $project.StartsWith('p03ci')) {
  throw 'P03 project name must begin p03test or p03ci'
}
$env:P03_PROJECT_NAME = $project
$files = @('-p', $project, '-f', 'compose.yaml', '-f', 'compose.runtime.yaml', '-f', 'compose.p03-isolated.yaml')
Push-Location $ProjectRoot
try {
  if (-not (Test-Path .env)) { throw 'Local .env is missing' }
  Write-Host "P03 EPHEMERAL project: $project" -ForegroundColor Cyan
  & docker compose @files config --quiet
  if ($LASTEXITCODE -ne 0) { throw 'P03 Compose merge invalid (requires Docker Compose v2.24+)' }
  & docker compose @files up -d --wait postgres rabbitmq
  if ($LASTEXITCODE -ne 0) { throw 'P03 PostgreSQL/RabbitMQ startup failed' }
  & docker compose @files up -d rabbitmq-init
  if ($LASTEXITCODE -ne 0) { throw 'P03 topology init failed' }
  & docker compose @files wait rabbitmq-init
  if ($LASTEXITCODE -ne 0) { throw 'P03 topology init returned nonzero' }
  & docker compose @files build room metering
  if ($LASTEXITCODE -ne 0) { throw 'P03 image build failed' }
  foreach ($svc in @('room','metering')) {
    & docker compose @files run --rm --no-deps $svc python -m alembic upgrade head
    if ($LASTEXITCODE -ne 0) { throw "P03 $svc migration failed" }
  }
  & docker compose @files up -d --wait room metering
  if ($LASTEXITCODE -ne 0) { throw 'P03 service startup failed' }

  # Publisher retry semantics, with both workers still stopped.
  & docker compose @files run --rm --no-deps room `
    sh -c 'python -m pip install --disable-pip-version-check -q -r /app/requirements-test.txt && python -m pytest -q integration/test_outbox_publish.py'
  if ($LASTEXITCODE -ne 0) { throw 'P03 real PostgreSQL publisher retry test failed' }

  & docker compose @files up -d room-outbox metering-consumer
  if ($LASTEXITCODE -ne 0) { throw 'P03 worker startup failed' }
  & docker compose @files run --rm --no-deps metering `
    sh -c 'python -m pip install --disable-pip-version-check -q -r /app/requirements-test.txt && python -m pytest -q tests/integration/test_outbox_and_events.py'
  if ($LASTEXITCODE -ne 0) { throw 'P03 RoomCreated -> RabbitMQ -> Metering end-to-end failed' }
  Write-Host 'P03 POSTGRES + RABBITMQ E2E OK: outbox retry, two meters, duplicate delivery' -ForegroundColor Green
} catch {
  Write-Host 'P03 E2E FAILED. Logs before cleanup:' -ForegroundColor Red
  & docker compose @files ps -a | Out-Host
  & docker compose @files logs --tail=100 room-outbox metering-consumer room metering rabbitmq | Out-Host
  throw
} finally {
  Write-Host "Removing ONLY isolated project: $project" -ForegroundColor Yellow
  & docker compose @files down -v --remove-orphans | Out-Host
  Remove-Item Env:P03_PROJECT_NAME -ErrorAction SilentlyContinue
  Pop-Location
}

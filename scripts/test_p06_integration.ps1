# REAL MQTT QoS1 -> RabbitMQ -> Metering -> PostgreSQL in a RANDOM disposable Compose project.
# NEVER down -v the normal rental-management project.
param([string]$ProjectRoot=(Split-Path -Parent $PSScriptRoot))
Set-StrictMode -Version Latest
$ErrorActionPreference='Stop'
$project='p06test'+([guid]::NewGuid().ToString('N').Substring(0,10))
if ($env:P06_CI_PROJECT_NAME) { $project=$env:P06_CI_PROJECT_NAME }
if (-not ($project.StartsWith('p06test') -or $project.StartsWith('p06ci'))) {
  throw 'Refusing unsafe P06 project name (must start p06test or p06ci)'
}
$env:P06_PROJECT_NAME=$project
$files=@('-p',$project,'-f','compose.yaml','-f','compose.p03.yaml',
         '-f','compose.p05.yaml','-f','compose.p06.yaml','-f','compose.p06-isolated.yaml')
Push-Location $ProjectRoot
try {
  if (-not (Test-Path '.env')) { throw 'Project .env missing' }
  Write-Host "P06 DISPOSABLE PROJECT: $project" -ForegroundColor Cyan
  & docker compose @files config --quiet
  if ($LASTEXITCODE -ne 0) { throw 'P06 Compose merge invalid (needs Compose v2.24+)' }
  & docker compose @files up -d --wait postgres rabbitmq
  if ($LASTEXITCODE -ne 0) { throw 'PostgreSQL/RabbitMQ startup failed' }
  & docker compose @files up -d rabbitmq-init
  if ($LASTEXITCODE -ne 0) { throw 'RabbitMQ bootstrap failed' }
  & docker compose @files wait rabbitmq-init
  if ($LASTEXITCODE -ne 0) { throw 'RabbitMQ queues/bindings init failed' }
  & docker compose @files build metering simulator
  if ($LASTEXITCODE -ne 0) { throw 'P06 build failed' }
  & docker compose @files run --rm --no-deps metering python -m alembic upgrade head
  if ($LASTEXITCODE -ne 0) { throw 'P06 Metering migration failed' }
  & docker compose @files up -d --wait metering
  if ($LASTEXITCODE -ne 0) { throw 'Metering HTTP readiness failed' }
  & docker compose @files up -d metering-telemetry-consumer
  if ($LASTEXITCODE -ne 0) { throw 'MQTT telemetry consumer failed to start' }
  & docker compose @files run --rm --no-deps metering python -m integration.seed_telemetry
  if ($LASTEXITCODE -ne 0) { throw 'Disposable meter seed failed' }
  & docker compose @files run --rm --no-deps simulator python -m app.main --once
  if ($LASTEXITCODE -ne 0) { throw 'Simulator MQTT QoS1 publish failed' }
  & docker compose @files run --rm --no-deps metering sh -c 'python -m pip install -q --disable-pip-version-check -r /app/requirements-test.txt paho-mqtt && python -m pytest -q integration/test_telemetry.py'
  if ($LASTEXITCODE -ne 0) { throw 'P06 real MQTT-to-PostgreSQL integration failed' }
  Write-Host 'P06 REAL E2E OK: simulator, QoS1, idempotency, conflict alert, out-of-order data' -ForegroundColor Green
} catch {
  Write-Host "P06 FAILURE: collecting disposable logs ($project):" -ForegroundColor Red
  & docker compose @files ps -a | Out-Host
  & docker compose @files logs --tail=100 metering-telemetry-consumer metering rabbitmq postgres | Out-Host
  throw
} finally {
  Write-Host "Cleaning ONLY disposable project: $project" -ForegroundColor Yellow
  & docker compose @files down -v --remove-orphans | Out-Host
  Remove-Item Env:P06_PROJECT_NAME -ErrorAction SilentlyContinue
  Pop-Location
}

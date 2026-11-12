# Real RabbitMQ events -> Metering + MQTT QoS1 -> PostgreSQL -> P07 cutoffs.
# Disposable random project. NEVER destroy your normal compose volumes.
param([string]$ProjectRoot=(Split-Path -Parent (Split-Path -Parent $PSScriptRoot)))
Set-StrictMode -Version Latest
$ErrorActionPreference='Stop'
$project='p07test'+([guid]::NewGuid().ToString('N').Substring(0,10))
if ($env:P07_CI_PROJECT_NAME) { $project=$env:P07_CI_PROJECT_NAME }
if (-not ($project.StartsWith('p07test') -or $project.StartsWith('p07ci'))) { throw 'Unsafe disposable P07 project name' }
$env:P07_PROJECT_NAME=$project
$files=@('-p',$project,'-f','compose.yaml', '-f', 'compose.workers.yaml','-f','infra/compose/tests/meter-cutoffs.yaml')
Push-Location $ProjectRoot
try {
  if (-not (Test-Path '.env')) { throw 'Missing .env' }
  Write-Host "P07 DISPOSABLE PROJECT: $project" -ForegroundColor Cyan
  & docker compose @files config --quiet
  if ($LASTEXITCODE -ne 0) { throw 'Invalid P07 Compose overlay' }
  & docker compose @files up -d --wait postgres rabbitmq
  if ($LASTEXITCODE -ne 0) { throw 'PostgreSQL or RabbitMQ unavailable' }
  & docker compose @files up -d rabbitmq-init
  if ($LASTEXITCODE -ne 0) { throw 'RabbitMQ bootstrap failed' }
  & docker compose @files wait rabbitmq-init
  if ($LASTEXITCODE -ne 0) { throw 'RabbitMQ queue setup failed' }
  & docker compose @files build metering
  if ($LASTEXITCODE -ne 0) { throw 'Metering image build failed' }
  & docker compose @files run --rm --no-deps metering python -m alembic upgrade head
  if ($LASTEXITCODE -ne 0) { throw 'Metering migration failed' }
  & docker compose @files up -d --wait metering
  if ($LASTEXITCODE -ne 0) { throw 'Metering API unhealthy' }
  & docker compose @files up -d metering-consumer metering-telemetry-consumer
  if ($LASTEXITCODE -ne 0) { throw 'Metering consumers failed to start' }
  & docker compose @files run --rm --no-deps metering sh -c 'python -m pip install -q --disable-pip-version-check -r /app/requirements-test.txt paho-mqtt && python -m pytest -q integration/test_cutoff_flow.py'
  if ($LASTEXITCODE -ne 0) { throw 'P07 real cutoff E2E failed' }
  Write-Host 'P07 E2E OK: domain events, real MQTT, VALID cutoff, version, offline' -ForegroundColor Green
} catch {
  Write-Host "P07 FAIL: collecting disposable container logs ($project)" -ForegroundColor Red
  & docker compose @files ps -a | Out-Host
  & docker compose @files logs --tail=100 metering metering-consumer metering-telemetry-consumer rabbitmq postgres | Out-Host
  throw
} finally {
  Write-Host "Cleaning ONLY disposable P07 project: $project" -ForegroundColor Yellow
  & docker compose @files down -v --remove-orphans | Out-Host
  Remove-Item Env:P07_PROJECT_NAME -ErrorAction SilentlyContinue
  Pop-Location
}

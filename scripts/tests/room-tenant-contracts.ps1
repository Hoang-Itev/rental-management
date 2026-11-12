# P04 REST + real PostgreSQL EXCLUDE concurrency test in randomized disposable project.
# NEVER performs 'down -v' on the user's regular rental-management project.
param([string]$ProjectRoot=(Split-Path -Parent (Split-Path -Parent $PSScriptRoot)))
Set-StrictMode -Version Latest
$ErrorActionPreference='Stop'
$project='p04test'+([guid]::NewGuid().ToString('N').Substring(0,10))
if ($env:P04_CI_PROJECT_NAME) { $project=$env:P04_CI_PROJECT_NAME }
if (-not ($project.StartsWith('p04test') -or $project.StartsWith('p04ci'))) { throw 'Unsafe P04 Docker project name' }
$env:P04_PROJECT_NAME=$project
$files=@('-p',$project,'-f','compose.yaml','-f','infra/compose/tests/room-tenant-contracts.yaml')
Push-Location $ProjectRoot
try {
  if (-not (Test-Path .env)) { throw 'Missing .env in project root (P04 isolated project uses its own volumes)' }
  Write-Host "P04 isolated project: $project" -ForegroundColor Cyan
  & docker compose @files config --quiet
  if ($LASTEXITCODE -ne 0) { throw 'Compose config invalid; Docker Compose v2.24+ required' }
  & docker compose @files up -d --wait postgres rabbitmq
  if ($LASTEXITCODE -ne 0) { throw 'Could not start isolated PostgreSQL/RabbitMQ' }
  & docker compose @files up -d rabbitmq-init
  if ($LASTEXITCODE -ne 0) { throw 'Could not initialize broker topology' }
  & docker compose @files wait rabbitmq-init
  if ($LASTEXITCODE -ne 0) { throw 'Broker topology init failed' }
  & docker compose @files build room tenant
  if ($LASTEXITCODE -ne 0) { throw 'Failed to build Room/Tenant' }
  foreach ($svc in @('room','tenant')) {
    & docker compose @files run --rm --no-deps $svc python -m alembic upgrade head
    if ($LASTEXITCODE -ne 0) { throw "$svc schema migration failed" }
  }
  & docker compose @files up -d --wait room tenant
  if ($LASTEXITCODE -ne 0) { throw 'Room/Tenant failed readiness' }
  & docker compose @files run --rm --no-deps tenant `
    sh -c 'python -m pip install --disable-pip-version-check -q -r /app/requirements-test.txt && python -m pytest -q integration/test_room_tenant.py'
  if ($LASTEXITCODE -ne 0) { throw 'P04 actual Room REST + tenant_db PostgreSQL integration failed' }
  Write-Host 'P04 INTEGRATION OK: Room REST + tenant_db EXCLUDE + inactive guard + terms' -ForegroundColor Green
} catch {
  Write-Host 'P04 integration failed. Logs:' -ForegroundColor Red
  & docker compose @files ps -a | Out-Host
  & docker compose @files logs --tail=100 room tenant postgres | Out-Host
  throw
} finally {
  Write-Host "Removing ONLY isolated P04 project: $project" -ForegroundColor Yellow
  & docker compose @files down -v --remove-orphans | Out-Host
  Remove-Item Env:P04_PROJECT_NAME -ErrorAction SilentlyContinue
  Pop-Location
}

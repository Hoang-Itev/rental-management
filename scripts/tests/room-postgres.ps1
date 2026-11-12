# Fresh isolated Compose project on the SAME Docker engine, NEVER the live rental-management volume.
# This script owns its randomly named temporary project. It intentionally cleans only that project.
param([string]$ProjectRoot = (Split-Path -Parent (Split-Path -Parent $PSScriptRoot)))
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$project = 'p02test' + ([guid]::NewGuid().ToString('N').Substring(0,10))
Push-Location $ProjectRoot
try {
  if (-not (Test-Path -LiteralPath .env)) { throw 'Local .env missing' }
  Write-Host "TEMPORARY test-only Compose project: $project" -ForegroundColor Cyan
  & docker compose -p $project -f compose.yaml up -d --wait postgres
  if ($LASTEXITCODE -ne 0) { throw 'Failed to start isolated PostgreSQL' }
  & docker compose -p $project -f compose.yaml build room
  if ($LASTEXITCODE -ne 0) { throw 'Failed to build Room image' }
  & docker compose -p $project -f compose.yaml run --rm --no-deps room python -m alembic upgrade head
  if ($LASTEXITCODE -ne 0) { throw 'Isolated room_db migration failed' }
  & docker compose -p $project -f compose.yaml -f infra/compose/tests/room-unit-and-db.yaml run --rm --no-deps room `
    sh -c 'python -m pip install --disable-pip-version-check -q -r /app/requirements-test.txt && python -m pytest integration -q'
  if ($LASTEXITCODE -ne 0) { throw 'Room PostgreSQL integration tests failed' }
  Write-Host 'ROOM POSTGRES INTEGRATION OK: isolated database; 5 tests' -ForegroundColor Green
} finally {
  # Project is random, prefixed p02test, never the default rental-management project.
  Write-Host "Cleaning ONLY isolated test project: $project" -ForegroundColor Yellow
  & docker compose -p $project -f compose.yaml down -v --remove-orphans --rmi local | Out-Host
  Pop-Location
}

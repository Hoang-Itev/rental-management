# Run from anywhere; builds 6 backend images, migrates 6 existing logical databases.
param(
  [string]$ProjectRoot = (Split-Path -Parent $PSScriptRoot),
  [switch]$SkipBuild
)
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$services = @('auth', 'room', 'tenant', 'metering', 'billing', 'notification')
Push-Location $ProjectRoot
try {
  docker compose ps --status running postgres | Out-Host
  if ($LASTEXITCODE -ne 0) { throw 'Docker Compose/Postgres check failed' }
  if (-not $SkipBuild) {
    Write-Host 'Building six service images (Python packages are installed INSIDE Docker images)...' -ForegroundColor Cyan
    & docker compose build @services
    if ($LASTEXITCODE -ne 0) { throw 'Docker image build failed. No migrations attempted.' }
  }
  foreach ($svc in $services) {
    Write-Host "`nApplying Alembic migration to ${svc}_db..." -ForegroundColor Cyan
    & docker compose run --rm --no-deps $svc python -m alembic upgrade head
    if ($LASTEXITCODE -ne 0) {
      throw "Migration failed for $svc; stopped. Previously migrated DBs are not rolled back. Inspect logs."
    }
  }
  Write-Host "`nChecking expected tables..." -ForegroundColor Cyan
  & (Join-Path $PSScriptRoot 'verify_schema_v3.ps1') -ProjectRoot $ProjectRoot
} finally {
  Pop-Location
}

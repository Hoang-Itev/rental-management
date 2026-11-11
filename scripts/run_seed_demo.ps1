# Direct, deterministic demo seed. Never run against production.
param(
  [string]$ProjectRoot = (Split-Path -Parent $PSScriptRoot),
  [switch]$SkipAuth
)
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
Push-Location $ProjectRoot
try {
  if (-not (Test-Path -LiteralPath '.env')) { throw '.env missing: create local .env first.' }

  # Always verify all six schemas first (even when intentionally skipping
  # the Auth demo account); prevents seeding into a partially migrated stack.
  & powershell -NoProfile -ExecutionPolicy Bypass -File (Join-Path $PSScriptRoot 'verify_schema_v3.ps1') -ProjectRoot $ProjectRoot
  if ($LASTEXITCODE -ne 0) { throw 'Schema verification failed. Seed was not started.' }

  $env:SEED_MODE = 'demo'
  if (-not $SkipAuth) {
    $secure = Read-Host 'Set a NEW demo owner login password (12+ characters; never stored in Git)' -AsSecureString
    $ptr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secure)
    try { $env:SEED_OWNER_PASSWORD = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($ptr) }
    finally { [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($ptr) }
    if ($env:SEED_OWNER_PASSWORD.Length -lt 12) { throw 'Password must contain at least 12 characters.' }
  }

  $services = @('room','tenant','metering','billing','notification')
  if (-not $SkipAuth) { $services = @('auth') + $services }

  Write-Host 'Seeding LOCAL demo snapshots (not via runtime business APIs)...' -ForegroundColor Cyan
  foreach ($svc in $services) {
    Write-Host "Seed service: $svc" -ForegroundColor Cyan
    & docker compose -f compose.yaml -f compose.seed.yaml run --rm --no-deps $svc python /seed/seed_service.py $svc
    if ($LASTEXITCODE -ne 0) { throw "Seed failed for $svc. Earlier services may already have committed." }
  }

  Write-Host 'Verifying the services included in this seed run...' -ForegroundColor Cyan
  & powershell -NoProfile -ExecutionPolicy Bypass -File (Join-Path $PSScriptRoot 'verify_seed_demo.ps1') -ProjectRoot $ProjectRoot -SkipAuth:$SkipAuth
  if ($LASTEXITCODE -ne 0) { throw 'Seed verification failed.' }
  Write-Host 'SEED OK. Running it again does not duplicate deterministic rows.' -ForegroundColor Green
} finally {
  Remove-Item Env:SEED_OWNER_PASSWORD -ErrorAction SilentlyContinue
  Remove-Item Env:SEED_MODE -ErrorAction SilentlyContinue
  Pop-Location
}

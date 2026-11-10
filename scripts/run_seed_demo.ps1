param(
  [string]$ProjectRoot = (Split-Path -Parent $PSScriptRoot),
  [switch]$SkipAuth
)
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
Push-Location $ProjectRoot
try {
  if (-not (Test-Path '.env')) { throw '.env missing: create local .env first.' }
  $env:SEED_MODE = 'demo'
  if (-not $SkipAuth) {
    $secure = Read-Host 'Set a NEW demo owner login password (12+ characters, never stored in repo)' -AsSecureString
    $ptr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secure)
    try { $env:SEED_OWNER_PASSWORD = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($ptr) }
    finally { [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($ptr) }
    if ($env:SEED_OWNER_PASSWORD.Length -lt 12) { throw 'Password must contain >=12 characters' }
  }
  $services = @('room','tenant','metering','billing','notification')
  if (-not $SkipAuth) { $services = @('auth') + $services }

  # Confirm all migrations were applied. Prevent partial/cross-environment seed.
  $checks = @(
    @('auth_db','auth_v3_001'),@('room_db','room_v3_001'),
    @('tenant_db','tenant_v3_001'),@('metering_db','metering_v3_001'),
    @('billing_db','billing_v3_001'),@('notification_db','notification_v3_001')
  )
  foreach ($entry in $checks) {
    $db = $entry[0]; $revision = $entry[1]
    $current = & docker compose exec -T postgres psql -U postgres -d $db -At -c 'SELECT version_num FROM alembic_version'
    if ($LASTEXITCODE -ne 0 -or ($current | Out-String).Trim() -ne $revision) {
      throw "$db migration not ready (expected $revision)"
    }
  }

  Write-Host 'Starting direct ORM snapshot seed into existing LOCAL databases...' -ForegroundColor Cyan
  foreach ($svc in $services) {
    Write-Host "`nSeed service: $svc" -ForegroundColor Cyan
    & docker compose -f compose.yaml -f compose.seed.yaml run --rm --no-deps `
      $svc python /seed/seed_service.py $svc
    if ($LASTEXITCODE -ne 0) { throw "Seeding failed at $svc; inspect logs. Previous services committed." }
  }
  Write-Host "`nVerifying seeded data (read-only)..." -ForegroundColor Cyan
  foreach ($svc in @('auth','room','tenant','metering','billing','notification')) {
    & docker compose -f compose.yaml -f compose.seed.yaml run --rm --no-deps `
      $svc python /seed/verify_service.py $svc
    if ($LASTEXITCODE -ne 0) { throw "Verification failed at $svc" }
  }
  Write-Host 'Demo seed completed and verified.' -ForegroundColor Green
} finally {
  Remove-Item Env:SEED_OWNER_PASSWORD -ErrorAction SilentlyContinue
  Remove-Item Env:SEED_MODE -ErrorAction SilentlyContinue
  Pop-Location
}

# Direct, deterministic demo seed. Never run against production.
param(
  [string]$ProjectRoot = (Split-Path -Parent $PSScriptRoot),
  [switch]$SkipAuth,
  [switch]$UseDemoPassword,
  [ValidateSet('presentation','baseline')][string]$Profile = 'presentation',
  [string]$AsOf,
  [switch]$SkipReminders
)
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
Push-Location $ProjectRoot
try {
  if (-not (Test-Path -LiteralPath '.env')) { throw '.env missing: create local .env first.' }
  $env:SEED_PROFILE = $Profile
  if ($Profile -eq 'presentation') {
    $running = @(& docker compose -f compose.yaml -f compose.workers.yaml --profile simulator ps --status running --services)
    if ($LASTEXITCODE -ne 0) { throw 'Cannot inspect running Compose services.' }
    $background = @($running | Where-Object { $_ -match '(outbox|consumer|scheduler|simulator|notification-worker)' })
    if ($background.Count -gt 0) { throw "Stop background services before seeding: $($background -join ', '). Follow scripts/seed/DEMO.md." }
    if (-not $AsOf) {
      if (Test-Path -LiteralPath '.seed-demo-date') { $AsOf = (Get-Content -LiteralPath '.seed-demo-date' -Raw).Trim() }
      else { $AsOf = (Get-Date).ToString('yyyy-MM-dd') }
    }
    [void][datetime]::ParseExact($AsOf, 'yyyy-MM-dd', [Globalization.CultureInfo]::InvariantCulture)
    if (Test-Path -LiteralPath '.seed-demo-date') {
      if ((Get-Content -LiteralPath '.seed-demo-date' -Raw).Trim() -ne $AsOf) { throw 'Demo date changed. Reset local data and remove .seed-demo-date first.' }
    }
    Set-Content -LiteralPath '.seed-demo-date' -Value $AsOf -Encoding Ascii
    $env:SEED_AS_OF = $AsOf
    Write-Host "Presentation data pinned to $AsOf. Real reminders will be queued after verification." -ForegroundColor Cyan
  }

  # Always verify all six schemas first (even when intentionally skipping
  # the Auth demo account); prevents seeding into a partially migrated stack.
  & (Join-Path $PSScriptRoot 'verify_schema_v3.ps1') -ProjectRoot $ProjectRoot

  $env:SEED_MODE = 'demo'
  if (-not $SkipAuth) {
    if ($UseDemoPassword) {
      $env:SEED_OWNER_PASSWORD = '123456789011'
    } else {
      $secure = Read-Host 'Set a NEW demo owner login password (12+ characters; never stored in Git)' -AsSecureString
      $ptr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secure)
      try { $env:SEED_OWNER_PASSWORD = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($ptr) }
      finally { [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($ptr) }
    }
    if ($env:SEED_OWNER_PASSWORD.Length -lt 12) { throw 'Password must contain at least 12 characters.' }
  }

  $services = @('room','tenant','metering','billing','notification')
  if (-not $SkipAuth) { $services = @('auth') + $services }

  Write-Host 'Seeding LOCAL demo snapshots (not via runtime business APIs)...' -ForegroundColor Cyan
  foreach ($svc in $services) {
    Write-Host "Seed service: $svc" -ForegroundColor Cyan
    & docker compose -f compose.yaml -f infra/compose/seed.yaml run --rm --no-deps $svc python /seed/seed_service.py $svc
    if ($LASTEXITCODE -ne 0) { throw "Seed failed for $svc. Earlier services may already have committed." }
  }

  Write-Host 'Verifying the services included in this seed run...' -ForegroundColor Cyan
  & (Join-Path $PSScriptRoot 'verify_seed_demo.ps1') -ProjectRoot $ProjectRoot -SkipAuth:$SkipAuth -Profile $Profile -AsOf $AsOf
  if ($Profile -eq 'presentation' -and -not $SkipReminders) {
    # Verification intentionally runs BEFORE enqueueing; delivery is left to runtime workers.
    & docker compose -f compose.yaml -f infra/compose/seed.yaml run --rm --no-deps billing python /seed/seed_service.py billing --queue-reminders
    if ($LASTEXITCODE -ne 0) { throw 'Seed loaded, but queueing reminders failed. Stop workers and inspect Billing.' }
  }
  Write-Host 'SEED OK. Running it again does not duplicate deterministic rows.' -ForegroundColor Green
} finally {
  Remove-Item Env:SEED_OWNER_PASSWORD -ErrorAction SilentlyContinue
  Remove-Item Env:SEED_MODE -ErrorAction SilentlyContinue
  Remove-Item Env:SEED_PROFILE, Env:SEED_AS_OF -ErrorAction SilentlyContinue
  Pop-Location
}

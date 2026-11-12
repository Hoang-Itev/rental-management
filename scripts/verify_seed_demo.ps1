param(
  [string]$ProjectRoot = (Split-Path -Parent $PSScriptRoot),
  [switch]$SkipAuth
)
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
Push-Location $ProjectRoot
try {
  $services = @('room','tenant','metering','billing','notification')
  if (-not $SkipAuth) { $services = @('auth') + $services }
  foreach ($svc in $services) {
    & docker compose -f compose.yaml -f infra/compose/seed.yaml run --rm --no-deps $svc python /seed/verify_service.py $svc
    if ($LASTEXITCODE -ne 0) { throw "Seed verification failed for $svc" }
  }
  Write-Host "SEED VERIFY OK: $($services -join ', ')" -ForegroundColor Green
} finally {
  Pop-Location
}

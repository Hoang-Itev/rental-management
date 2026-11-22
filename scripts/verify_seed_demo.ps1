param(
  [string]$ProjectRoot = (Split-Path -Parent $PSScriptRoot),
  [switch]$SkipAuth,
  [ValidateSet('presentation','baseline')][string]$Profile,
  [string]$AsOf
)
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$previousProfile = $env:SEED_PROFILE
$previousAsOf = $env:SEED_AS_OF
Push-Location $ProjectRoot
try {
  if (-not $Profile) {
    if (Test-Path -LiteralPath '.seed-demo-date') { $Profile = 'presentation' }
    else { $Profile = 'baseline' }
  }
  $env:SEED_PROFILE = $Profile
  if ($Profile -eq 'presentation') {
    if (-not $AsOf) { $AsOf = (Get-Content -LiteralPath '.seed-demo-date' -Raw).Trim() }
    $env:SEED_AS_OF = $AsOf
  }
  $services = @('room','tenant','metering','billing','notification')
  if (-not $SkipAuth) { $services = @('auth') + $services }
  foreach ($svc in $services) {
    & docker compose -f compose.yaml -f infra/compose/seed.yaml run --rm --no-deps $svc python /seed/verify_service.py $svc
    if ($LASTEXITCODE -ne 0) { throw "Seed verification failed for $svc" }
  }
  Write-Host "SEED VERIFY OK: $($services -join ', ')" -ForegroundColor Green
} finally {
  if ($null -eq $previousProfile) { Remove-Item Env:SEED_PROFILE -ErrorAction SilentlyContinue }
  else { $env:SEED_PROFILE = $previousProfile }
  if ($null -eq $previousAsOf) { Remove-Item Env:SEED_AS_OF -ErrorAction SilentlyContinue }
  else { $env:SEED_AS_OF = $previousAsOf }
  Pop-Location
}

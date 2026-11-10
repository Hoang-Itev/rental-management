param([string]$ProjectRoot = (Split-Path -Parent $PSScriptRoot))
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
Push-Location $ProjectRoot
try {
  foreach ($svc in @('auth','room','tenant','metering','billing','notification')) {
    & docker compose -f compose.yaml -f compose.seed.yaml run --rm --no-deps `
       $svc python /seed/verify_service.py $svc
    if ($LASTEXITCODE -ne 0) { throw "Verify failed: $svc" }
  }
} finally { Pop-Location }

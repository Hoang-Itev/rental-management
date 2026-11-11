# Read-only Gateway checkpoint: needs an active meter and an OWNER account.
param([string]$ProjectRoot=(Split-Path -Parent $PSScriptRoot))
Set-StrictMode -Version Latest
$ErrorActionPreference='Stop'
Push-Location $ProjectRoot
try {
  if (-not (Test-Path '.env')) { throw 'Missing project .env' }
  $line=Get-Content '.env' | Where-Object { $_ -match '^OWNER_EMAIL=' } | Select-Object -First 1
  if (-not $line) { throw 'Missing OWNER_EMAIL in .env' }
  $env:TEST_AUTH_EMAIL=($line -split '=',2)[1].Trim()
  $sql="SELECT id FROM meters WHERE status='ACTIVE' ORDER BY id LIMIT 1;"
  $rows=@(& docker compose exec -T postgres psql -X -A -t -q -U postgres -d metering_db -c $sql)
  if ($LASTEXITCODE -ne 0) { throw 'Could not query metering_db for demo meter' }
  $id=($rows -join '').Trim()
  if (-not $id) { throw 'No ACTIVE meter exists yet. Create a Room and let RoomCreated provision its meters first.' }
  $env:P06_METER_ID=$id
  $pwd=Read-Host 'Existing owner password (P06 Gateway test is read-only)' -AsSecureString
  $ptr=[Runtime.InteropServices.Marshal]::SecureStringToBSTR($pwd)
  try { $env:TEST_AUTH_PASSWORD=[Runtime.InteropServices.Marshal]::PtrToStringBSTR($ptr) }
  finally { [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($ptr) }
  & python '.\scripts\p06\gateway_check.py'
  if ($LASTEXITCODE -ne 0) { throw 'P06 Gateway checkpoint FAILED' }
} finally {
  Remove-Item Env:P06_METER_ID -ErrorAction SilentlyContinue
  Remove-Item Env:TEST_AUTH_EMAIL -ErrorAction SilentlyContinue
  Remove-Item Env:TEST_AUTH_PASSWORD -ErrorAction SilentlyContinue
  Pop-Location
}

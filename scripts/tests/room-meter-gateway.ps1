# End-to-end with EXISTING owner; inserts one new demo property/tree/room into local DB.
param([string]$ProjectRoot = (Split-Path -Parent (Split-Path -Parent $PSScriptRoot)))
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
Push-Location $ProjectRoot
try {
  $line = Get-Content '.env' | Where-Object { $_ -match '^OWNER_EMAIL=' } | Select-Object -First 1
  if (-not $line) { throw 'OWNER_EMAIL missing in .env' }
  $env:TEST_AUTH_EMAIL = ($line -split '=',2)[1].Trim()
  $secret = Read-Host 'Existing Auth owner password (P03 creates 1 demo tree)' -AsSecureString
  $ptr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secret)
  try { $env:TEST_AUTH_PASSWORD = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($ptr) }
  finally { [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($ptr) }
  & python '.\scripts\tests\gateway\room_meter.py'
  if ($LASTEXITCODE -ne 0) { throw 'P03 Gateway checkpoint failed' }
} finally {
  Remove-Item Env:TEST_AUTH_EMAIL -ErrorAction SilentlyContinue
  Remove-Item Env:TEST_AUTH_PASSWORD -ErrorAction SilentlyContinue
  Pop-Location
}

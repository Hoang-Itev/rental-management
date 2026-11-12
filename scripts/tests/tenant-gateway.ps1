# Persistent demo via existing owner JWT. Run ONLY after Tenant/Room are healthy in local stack.
param([string]$ProjectRoot=(Split-Path -Parent (Split-Path -Parent $PSScriptRoot)))
Set-StrictMode -Version Latest
$ErrorActionPreference='Stop'
Push-Location $ProjectRoot
try {
  $line=Get-Content '.env' | Where-Object { $_ -match '^OWNER_EMAIL=' } | Select-Object -First 1
  if (-not $line) { throw 'Missing OWNER_EMAIL in .env' }
  $env:TEST_AUTH_EMAIL=($line -split '=',2)[1].Trim()
  $secret=Read-Host 'Existing owner password (P04 creates real local demo records)' -AsSecureString
  $ptr=[Runtime.InteropServices.Marshal]::SecureStringToBSTR($secret)
  try { $env:TEST_AUTH_PASSWORD=[Runtime.InteropServices.Marshal]::PtrToStringBSTR($ptr) }
  finally { [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($ptr) }
  & python '.\scripts\tests\gateway\tenant.py'
  if ($LASTEXITCODE -ne 0) { throw 'P04 Gateway E2E failed' }
} finally {
  Remove-Item Env:TEST_AUTH_EMAIL -ErrorAction SilentlyContinue
  Remove-Item Env:TEST_AUTH_PASSWORD -ErrorAction SilentlyContinue
  Pop-Location
}

# Read-only P02 Gateway integration; uses existing seeded owner, no DB edits from Room APIs.
param([string]$ProjectRoot = (Split-Path -Parent $PSScriptRoot))
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
Push-Location $ProjectRoot
try {
  $line = Get-Content '.env' | Where-Object { $_ -match '^OWNER_EMAIL=' } | Select-Object -First 1
  if (-not $line) { throw 'OWNER_EMAIL missing from .env' }
  $env:TEST_AUTH_EMAIL = ($line -split '=',2)[1].Trim()
  $secret=Read-Host 'Existing Auth owner password' -AsSecureString
  $ptr=[Runtime.InteropServices.Marshal]::SecureStringToBSTR($secret)
  try { $env:TEST_AUTH_PASSWORD=[Runtime.InteropServices.Marshal]::PtrToStringBSTR($ptr) }
  finally { [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($ptr) }
  & python '.\scripts\room\gateway_check.py'
  if ($LASTEXITCODE -ne 0) { throw 'Room gateway test failed' }
} finally {
  Remove-Item Env:TEST_AUTH_EMAIL -ErrorAction SilentlyContinue
  Remove-Item Env:TEST_AUTH_PASSWORD -ErrorAction SilentlyContinue
  Pop-Location
}

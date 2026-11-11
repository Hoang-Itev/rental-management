# P01 gateway integration. Runs against CURRENT local stack; does not seed/reset DB.
param([string]$ProjectRoot = (Split-Path -Parent $PSScriptRoot))
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
# Script lives in scripts/, so ProjectRoot default = project root.
Push-Location $ProjectRoot
try {
  if (-not (Test-Path -LiteralPath '.env')) { throw '.env not found in project root' }
  $ownerLine = Get-Content -LiteralPath '.env' | Where-Object { $_ -match '^OWNER_EMAIL=' } | Select-Object -First 1
  if (-not $ownerLine) { throw 'OWNER_EMAIL missing in .env' }
  $env:TEST_AUTH_EMAIL = ($ownerLine -split '=',2)[1].Trim()
  $secret = Read-Host 'Enter the EXISTING seeded Auth owner password' -AsSecureString
  $ptr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secret)
  try { $env:TEST_AUTH_PASSWORD = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($ptr) }
  finally { [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($ptr) }
  & python '.\scripts\auth\gateway_check.py'
  if ($LASTEXITCODE -ne 0) { throw 'Gateway integration failed' }
} finally {
  Remove-Item Env:TEST_AUTH_EMAIL -ErrorAction SilentlyContinue
  Remove-Item Env:TEST_AUTH_PASSWORD -ErrorAction SilentlyContinue
  Pop-Location
}

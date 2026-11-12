# Uses EXISTING local PostgreSQL data, creates ONE persistent demo tree.
param([string]$ProjectRoot=(Split-Path -Parent (Split-Path -Parent $PSScriptRoot)))
Set-StrictMode -Version Latest
$ErrorActionPreference='Stop'
Push-Location $ProjectRoot
try {
  $line=Get-Content '.env' | Where-Object { $_ -match '^OWNER_EMAIL=' } | Select-Object -First 1
  if (-not $line) { throw 'OWNER_EMAIL not found in the project .env' }
  $env:TEST_AUTH_EMAIL=($line -split '=',2)[1].Trim()
  $secret=Read-Host 'Existing owner password (P05 leaves real local demo records)' -AsSecureString
  $ptr=[Runtime.InteropServices.Marshal]::SecureStringToBSTR($secret)
  try { $env:TEST_AUTH_PASSWORD=[Runtime.InteropServices.Marshal]::PtrToStringBSTR($ptr) }
  finally { [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($ptr) }
  & python '.\scripts\tests\gateway\contract_lifecycle.py'
  if ($LASTEXITCODE -ne 0) { throw 'P05 local Gateway checkpoint FAILED' }
} finally {
  Remove-Item Env:TEST_AUTH_EMAIL -ErrorAction SilentlyContinue
  Remove-Item Env:TEST_AUTH_PASSWORD -ErrorAction SilentlyContinue
  Pop-Location
}

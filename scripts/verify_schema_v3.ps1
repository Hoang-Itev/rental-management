# Windows PowerShell 5.1 compatible. Checks each DB revision against the Alembic
# head in the corresponding Docker image (never hard-codes *_001 / *_002 / *_003).
param([string]$ProjectRoot = (Split-Path -Parent $PSScriptRoot))
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$expected = [ordered]@{
  auth         = 1
  room         = 6
  tenant       = 5
  metering     = 5
  billing      = 8
  notification = 1
}

function Invoke-DockerChecked {
  param([string[]]$Arguments, [string]$Description)
  $output = & docker @Arguments
  if ($LASTEXITCODE -ne 0) { throw "$Description failed (exit code $LASTEXITCODE)." }
  return @($output)
}

Push-Location $ProjectRoot
try {
  $total = 0
  foreach ($service in $expected.Keys) {
    $db = "${service}_db"

    # Alembic may print multiple lines if branches exist. This project requires
    # exactly one head in each independent service.
    $headOutput = @(Invoke-DockerChecked -Arguments @('compose','run','--rm','--no-deps',$service,'python','-m','alembic','heads') -Description "alembic heads for $service")
    $heads = @()
    foreach ($line in $headOutput) {
      if ($line -match '^\s*([A-Za-z0-9_]+)\s+\(head\)\s*$') { $heads += $Matches[1] }
    }
    if ($heads.Count -ne 1) {
      throw "${service}: expected exactly one Alembic head. Output: $($headOutput -join '; ')"
    }
    $head = [string]$heads[0]

    $sql = "SELECT count(*) FROM pg_catalog.pg_tables WHERE schemaname='public' AND tablename <> 'alembic_version';"
    $rawCount = @(Invoke-DockerChecked -Arguments @('compose','exec','-T','postgres','psql','-X','-q','-A','-t','-U','postgres','-d',$db,'-c',$sql) -Description "count business tables in $db")
    $countText = ($rawCount -join "`n").Trim()
    $count = 0
    if (-not [int]::TryParse($countText, [ref]$count)) { throw "${db}: invalid table count: $countText" }
    $should = [int]$expected[$service]
    if ($count -ne $should) { throw "${db}: expected $should business tables; found $count" }

    $rawRevision = @(Invoke-DockerChecked -Arguments @('compose','exec','-T','postgres','psql','-X','-q','-A','-t','-U','postgres','-d',$db,'-c','SELECT version_num FROM alembic_version;') -Description "read alembic_version in $db")
    $revision = ($rawRevision -join "`n").Trim()
    if ($revision -ne $head) {
      throw "${db}: DB revision '$revision' differs from image head '$head'. Rebuild images / apply migration before seeding."
    }
    Write-Host "$db : $count business tables, Alembic $revision (head)" -ForegroundColor Green
    $total += $count
  }
  Write-Host "SCHEMA OK: $total/26 business tables; 6 Alembic heads matched." -ForegroundColor Green
} finally {
  Pop-Location
}

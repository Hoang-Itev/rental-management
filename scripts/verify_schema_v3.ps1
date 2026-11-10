param([string]$ProjectRoot = (Split-Path -Parent $PSScriptRoot))
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$expected = [ordered]@{
  auth_db=1
  room_db=6
  tenant_db=5
  metering_db=5
  billing_db=8
  notification_db=1
}
Push-Location $ProjectRoot
try {
  $sum=0
  foreach ($database in $expected.Keys) {
    $sql = "SELECT count(*) FROM pg_catalog.pg_tables WHERE schemaname = 'public' AND tablename <> 'alembic_version';"
    $raw = & docker compose exec -T postgres psql -X -q -A -t -U postgres -d $database -c $sql
    if ($LASTEXITCODE -ne 0) { throw "psql failed: $database" }
    $value = [int]($raw | Select-Object -Last 1).Trim()
    $should = [int]$expected[$database]
    if ($value -ne $should) { throw "${database}: expected $should business tables, actual $value" }
    $ver = & docker compose exec -T postgres psql -X -q -A -t -U postgres -d $database -c 'SELECT version_num FROM alembic_version;'
    if ($LASTEXITCODE -ne 0) { throw "No alembic_version on $database" }
    if (-not ($ver -like '*_v3_001')) { throw "$database unexpected alembic version: $ver" }
    Write-Host "$database : $value tables + alembic_version $ver" -ForegroundColor Green
    $sum += $value
  }
  Write-Host "TOTAL: $sum/26 business tables + 6 alembic_version tables" -ForegroundColor Green
} finally {
  Pop-Location
}

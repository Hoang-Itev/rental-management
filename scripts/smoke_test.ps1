# READ-ONLY smoke test of a running Docker Compose stack. Never drops volumes.
# PowerShell 5.1 and PowerShell 7 compatible. Assumes `docker compose up -d`
# was already executed. CI runs it against a new isolated Docker environment.
param(
  [string]$ProjectRoot = (Split-Path -Parent $PSScriptRoot),
  [int]$TimeoutSeconds = 180,
  [switch]$Runtime
)
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
if ($TimeoutSeconds -lt 1) { throw 'TimeoutSeconds must be at least 1.' }

$migrations = @('auth-migrate', 'room-migrate', 'tenant-migrate', 'metering-migrate', 'billing-migrate', 'notification-migrate')
$appServices = @('auth', 'room', 'tenant', 'metering', 'billing', 'notification')
$composeArgs = @('-f', 'compose.yaml')
$workers = @()
if ($Runtime) {
  $workers = @('room-outbox', 'metering-consumer', 'tenant-outbox', 'tenant-scheduler',
               'room-consumer', 'metering-telemetry-consumer', 'metering-cutoff-scheduler',
               'billing-scheduler', 'billing-outbox', 'notification-worker')
}

function Get-ServiceContainer {
  param([string]$Service)
  $result = & docker compose @composeArgs ps -a -q $Service
  if ($LASTEXITCODE -ne 0) { throw "docker compose ps failed: $Service" }
  return (($result | Out-String).Trim())
}

function Get-State {
  param([string]$ContainerId)
  if (-not $ContainerId) { return 'missing' }
  $value = & docker inspect --format '{{.State.Status}}|{{.State.ExitCode}}' $ContainerId
  if ($LASTEXITCODE -ne 0) { return 'inspect_failed' }
  return (($value | Out-String).Trim())
}

function Get-Health {
  param([string]$ContainerId)
  if (-not $ContainerId) { return 'missing' }
  $value = & docker inspect --format '{{if .State.Health}}{{.State.Health.Status}}{{else}}no_healthcheck{{end}}' $ContainerId
  if ($LASTEXITCODE -ne 0) { return 'inspect_failed' }
  return (($value | Out-String).Trim())
}

Push-Location $ProjectRoot
try {
  $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
  $reason = ''
  do {
    $issues = New-Object 'System.Collections.Generic.List[string]'

    foreach ($svc in $migrations + @('rabbitmq-init')) {
      $id = Get-ServiceContainer $svc
      $state = Get-State $id
      if ($state -ne 'exited|0') { $issues.Add("${svc}: $state (expected exited|0)") }
    }

    foreach ($svc in @('postgres','rabbitmq','mailpit') + $appServices) {
      $id = Get-ServiceContainer $svc
      $state = Get-State $id
      $health = Get-Health $id
      if ($state -notlike 'running|*' -or $health -ne 'healthy') {
        $issues.Add("${svc}: $state / $health (expected running / healthy)")
      }
    }

    foreach ($svc in $workers) {
      $state = Get-State (Get-ServiceContainer $svc)
      if ($state -notlike 'running|*') { $issues.Add("${svc}: $state (expected running)") }
    }

    $nginxId = Get-ServiceContainer 'nginx'
    if ((Get-State $nginxId) -notlike 'running|*') { $issues.Add('nginx is not running') }

    try {
      $response = Invoke-WebRequest -Uri 'http://127.0.0.1:8080/gateway-health' -UseBasicParsing -TimeoutSec 4
      if ([int]$response.StatusCode -ne 200) { $issues.Add("Gateway returned HTTP $($response.StatusCode)") }
    } catch {
      $issues.Add('GET http://127.0.0.1:8080/gateway-health failed')
    }

    if ($issues.Count -eq 0) {
      Write-Host 'SMOKE OK: 6 migrations exited(0); rabbitmq-init exited(0); 6 apps healthy; postgres/rabbitmq/mailpit healthy; Nginx HTTP 200.' -ForegroundColor Green
      if ($Runtime) { Write-Host "RUNTIME OK: $($workers.Count) workers and schedulers running." -ForegroundColor Green }
      return
    }
    $reason = $issues -join '; '
    if ((Get-Date) -ge $deadline) { break }
    Start-Sleep -Seconds 4
  } while ($true)
  throw "SMOKE FAILED: $reason"
} finally {
  Pop-Location
}

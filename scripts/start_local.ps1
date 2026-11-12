[CmdletBinding()]
param(
    [switch]$SeedDemo,
    [switch]$SyncEnv
)

$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot

function Invoke-LocalCompose {
    & docker compose -f compose.yaml -f compose.workers.yaml @args
    if ($LASTEXITCODE -ne 0) { throw "Docker Compose failed (exit $LASTEXITCODE)." }
}

Push-Location -LiteralPath $root
try {
    if ($SyncEnv -and (Test-Path -LiteralPath '.env')) {
        $backup = '.env.backup-' + [Guid]::NewGuid().ToString('N')
        Copy-Item -LiteralPath '.env' -Destination $backup
        Write-Host "Saved previous local configuration to $backup"
    }
    if ($SyncEnv -or -not (Test-Path -LiteralPath '.env')) {
        Copy-Item -LiteralPath '.env.example' -Destination '.env' -Force
    }

    if ($SeedDemo) {
        Invoke-LocalCompose up -d --build --wait auth room tenant metering billing notification
        & (Join-Path $PSScriptRoot 'run_seed_demo.ps1') -UseDemoPassword
        if (-not $?) { throw 'Local demo seed failed.' }
    }
    Invoke-LocalCompose up -d --build --wait
} finally {
    Pop-Location
}

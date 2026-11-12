# Service unit tests and isolated integration tests. Use Docker Desktop in Linux container mode.
[CmdletBinding()]
param([switch]$UnitOnly)

$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
$project = 'rental-local-unit-' + [Guid]::NewGuid().ToString('N').Substring(0, 10)
$composeArgs = @('--env-file', '.env.example', '-p', $project, '-f', 'compose.yaml')
$services = [ordered]@{
    auth = 'backend/auth'
    room = 'backend/services/room'
    tenant = 'backend/services/tenant'
    metering = 'backend/services/metering'
    billing = 'backend/services/billing'
    notification = 'backend/services/notification'
    simulator = 'simulator'
}
$integrations = @(
    'test_room_postgres.ps1',
    'test_p03_integration.ps1',
    'test_p04_integration.ps1',
    'test_p05_integration.ps1',
    'test_p06_integration.ps1',
    'test_p07_integration.ps1',
    'test_p09.ps1',
    'test_p10.ps1',
    'test_p11.ps1',
    'test_p12.ps1'
)

function Invoke-UnitCompose {
    & docker compose @composeArgs @args
    if ($LASTEXITCODE -ne 0) { throw "Unit Compose command failed (exit $LASTEXITCODE)." }
}

Push-Location -LiteralPath $root
try {
    if (-not $UnitOnly -and -not (Test-Path -LiteralPath '.env')) {
        throw 'Create local .env from .env.example before running the isolated integration scripts.'
    }

    foreach ($entry in $services.GetEnumerator()) {
        Write-Host "Unit tests: $($entry.Key)"
        $path = Join-Path $root $entry.Value
        $mount = "${path}:/checkout:ro"
        $requirements = "$(Join-Path $root 'requirements-test.txt'):/requirements-test.txt:ro"
        $testCommand = 'python -m pip install -q -r /requirements-test.txt && cd /checkout && PYTHONDONTWRITEBYTECODE=1 python -m pytest -q -p no:cacheprovider tests'
        Invoke-UnitCompose run --rm --no-deps --build --volume $mount --volume $requirements $entry.Key sh -ec $testCommand
    }

    if (-not $UnitOnly) {
        foreach ($script in $integrations) {
            Write-Host "Isolated integration: $script"
            & (Join-Path $PSScriptRoot $script)
            if (-not $?) { throw "Integration script failed: $script" }
        }
    }

    Write-Host 'Local test suite passed.' -ForegroundColor Green
} finally {
    & docker compose @composeArgs --profile simulator down --remove-orphans
    Pop-Location
}

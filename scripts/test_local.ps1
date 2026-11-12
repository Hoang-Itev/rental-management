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
    'tests/room-postgres-integration.ps1',
    'tests/room-meter-events-integration.ps1',
    'tests/room-tenant-contracts-integration.ps1',
    'tests/contract-lifecycle-integration.ps1',
    'tests/mqtt-telemetry-integration.ps1',
    'tests/meter-cutoffs-integration.ps1',
    'tests/billing-invoices-integration.ps1',
    'tests/invoice-email-integration.ps1',
    'tests/momo-payments-integration.ps1',
    'tests/notification-rules-integration.ps1'
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
        $config = "$(Join-Path $root 'pyproject.toml'):/pytest-config.toml:ro"
        $coverageArgs = switch ($entry.Key) {
            'auth' { '--cov=app --cov-fail-under=95' }
            'room' { '--cov=app --cov-fail-under=95' }
            'billing' { '--cov=app.calculator --cov-fail-under=80' }
            'simulator' { '' }
            default { '--cov=app.service --cov-fail-under=80' }
        }
        $testCommand = 'cd /checkout && PYTHONDONTWRITEBYTECODE=1 COVERAGE_FILE=/tmp/.coverage python -m pytest -c /pytest-config.toml -q -p no:cacheprovider tests ' + $coverageArgs
        if ($entry.Key -ne 'simulator') {
            $testCommand = "python /repo/scripts/check_api_contract.py --service $($entry.Key) && " + $testCommand
        }
        $testCommand = 'python -m pip install -q -r /requirements-test.txt && ' + $testCommand
        Invoke-UnitCompose run --rm --no-deps --build --volume "${root}:/repo:ro" --volume $mount --volume $requirements --volume $config $entry.Key sh -ec $testCommand
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
    & docker compose @composeArgs --profile simulator down --remove-orphans --rmi local
    Pop-Location
}

[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$project = 'rental-p12-test-' + [Guid]::NewGuid().ToString('N').Substring(0, 12)
$composeArgs = @('--env-file', '.env.example', '-p', $project, '-f', 'compose.yaml', '-f', 'compose.workers.yaml',
    '-f', 'infra/compose/tests/notification-rules.yaml')

function Invoke-P12Compose {
    & docker compose @composeArgs @args
    if ($LASTEXITCODE -ne 0) { throw "P12 Compose command failed (exit $LASTEXITCODE)." }
}

Push-Location $root
try {
    try {
        Invoke-P12Compose up -d --build --wait --wait-timeout 240 mailpit billing-outbox tenant-outbox tenant notification
        Invoke-P12Compose run --rm --no-deps notification sh -ec 'python -m pip install -q -r /p12/requirements-test.txt && PYTHONPATH=/app python -m pytest -q /app/tests /p12/integration/test_notification_rules.py'
    } finally {
        Invoke-P12Compose down -v --remove-orphans --rmi local
    }
} finally {
    Pop-Location
}

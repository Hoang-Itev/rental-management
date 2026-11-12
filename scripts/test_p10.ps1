[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
$project = 'rental-p10-test-' + [Guid]::NewGuid().ToString('N').Substring(0, 12)
$composeArgs = @('--env-file', '.env.example', '-p', $project, '-f', 'compose.yaml',
    '-f', 'compose.runtime.yaml', '-f', 'compose.p10-test.yaml')

function Invoke-P10Compose {
    & docker compose @composeArgs @args
    if ($LASTEXITCODE -ne 0) { throw "P10 Compose command failed (exit $LASTEXITCODE)." }
}

Push-Location $root
try {
    try {
        Invoke-P10Compose up -d --build --wait --wait-timeout 240 nginx mailpit billing-outbox
        Invoke-P10Compose run --rm --no-deps notification sh -ec 'python -m pip install -q -r /p10/requirements-test.txt && PYTHONPATH=/app python -m pytest -q /app/tests /p10/integration/test_outbox_and_events.py'
    } finally {
        Invoke-P10Compose down -v --remove-orphans
    }
} finally {
    Pop-Location
}

[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
$project = 'rental-p09-test-' + [Guid]::NewGuid().ToString('N').Substring(0, 12)
$composeArgs = @('--env-file', '.env.example', '-p', $project, '-f', 'compose.yaml', '-f', 'infra/compose/tests/billing-invoices.yaml')

function Invoke-P09Compose {
    & docker compose @composeArgs @args
    if ($LASTEXITCODE -ne 0) { throw "P09 Compose command failed (exit $LASTEXITCODE)." }
}

Push-Location $root
try {
    & docker compose version
    if ($LASTEXITCODE -ne 0) { throw 'Docker Compose is required.' }
    try {
        Invoke-P09Compose up -d --build --wait --wait-timeout 180 tenant metering billing
        Invoke-P09Compose run --rm --no-deps billing sh -ec 'python -m pip install -q -r /p09/requirements-test.txt && PYTHONPATH=/app python -m pytest -q /app/tests /p09/integration/test_contract_billing.py'
    } finally {
        Invoke-P09Compose down -v --remove-orphans
    }
} finally {
    Pop-Location
}

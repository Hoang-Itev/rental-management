[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
$project = 'rental-p11-test-' + [Guid]::NewGuid().ToString('N').Substring(0, 12)
$composeArgs = @('--env-file', '.env.example', '-p', $project, '-f', 'compose.yaml',
    '-f', 'compose.p11-test.yaml')

function Invoke-P11Compose {
    & docker compose @composeArgs @args
    if ($LASTEXITCODE -ne 0) { throw "P11 Compose command failed (exit $LASTEXITCODE)." }
}

Push-Location $root
try {
    try {
        Invoke-P11Compose up -d --build --wait --wait-timeout 240 billing
        Invoke-P11Compose run --rm --no-deps billing sh -ec 'python -m pip install -q -r /p11/requirements-test.txt && PYTHONPATH=/app python -m pytest -q /app/tests /p11/integration/test_momo_payment.py'
    } finally {
        Invoke-P11Compose down -v --remove-orphans
    }
} finally {
    Pop-Location
}

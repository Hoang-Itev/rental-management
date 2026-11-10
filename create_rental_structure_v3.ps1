# Rental Management - Monorepo Scaffold V3 (PowerShell 5.1 / 7+)
# Creates a COMPLETE STARTER FILE INVENTORY, not production-ready implementation.
# Safe to run repeatedly: existing NON-EMPTY files are never overwritten.
# Default location matches the path provided by the project owner.
# Run: powershell -NoProfile -ExecutionPolicy Bypass -File .\create_rental_structure_v3.ps1
# Override: powershell -NoProfile -ExecutionPolicy Bypass -File .\create_rental_structure_v3.ps1 -ProjectRoot 'D:\work\rental-management'

param(
    [string]$ProjectRoot = 'C:\Users\hoang\Documents\learn-space\cloud\rental-management'
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

if ([System.IO.Path]::IsPathRooted($ProjectRoot)) {
    $root = [System.IO.Path]::GetFullPath($ProjectRoot)
} else {
    $root = [System.IO.Path]::GetFullPath((Join-Path -Path (Get-Location).Path -ChildPath $ProjectRoot))
}

$null = New-Item -ItemType Directory -Path $root -Force

# Only folders that are intentionally empty at initial creation.
$emptyDirectories = @(
    'frontend',                     # FE team creates their own React project
    'infra/k8s/manifests'           # Optional kind practice, not in P0
)

# Repository-level files. No need to create them manually later.
$rootFiles = @(
    'README.md', '.gitignore', '.gitattributes', '.editorconfig', '.env.example',
    'pyproject.toml', 'requirements-dev.txt',
    'compose.yaml', 'compose.dev.yaml', 'compose.prod.yaml',

    'contracts/openapi.yaml', 'contracts/asyncapi.yaml',

    'docs/PROJECT_CONTEXT.md',
    'docs/SYSTEM_DESIGN.md',
    'docs/DATABASE_DESIGN_V3.md',
    'docs/API_EVENT_CONTRACTS_CONTEXT.md',
    'docs/AI_MAP.md',
    'docs/services/auth.md',
    'docs/services/room.md',
    'docs/services/tenant.md',
    'docs/services/metering.md',
    'docs/services/billing.md',
    'docs/services/notification.md',
    'docs/flows/contract_lifecycle.md',
    'docs/flows/billing_cycle.md',
    'docs/flows/momo_payment.md',

    'api-requests/admin.http',
    'api-requests/internal.http',
    'api-requests/public_payment.http',

    'infra/nginx/Dockerfile',
    'infra/nginx/default.conf',
    'infra/postgres/init/01-create-databases.sh',
    'infra/rabbitmq/rabbitmq.conf',
    'infra/rabbitmq/enabled_plugins',
    'infra/rabbitmq/definitions.json',
    'infra/terraform/versions.tf',
    'infra/terraform/main.tf',
    'infra/terraform/variables.tf',
    'infra/terraform/outputs.tf',
    'infra/terraform/terraform.tfvars.example',
    'infra/terraform/user_data.sh.tftpl',
    'infra/k8s/README.md',

    '.github/workflows/ci.yml',
    '.github/workflows/publish.yml',
    '.github/workflows/deploy.yml',
    '.github/pull_request_template.md',

    'scripts/export_context.py',
    'scripts/check_contracts.py',
    'scripts/smoke_test.ps1',

    'simulator/Dockerfile',
    'simulator/.dockerignore',
    'simulator/requirements.txt',
    'simulator/app/__init__.py',
    'simulator/app/config.py',
    'simulator/app/main.py',
    'simulator/app/meter_client.py',
    'simulator/app/mqtt_client.py',
    'simulator/app/virtual_clock.py',
    'simulator/tests/test_simulator.py',

    'tests/integration/test_contract_billing.py',
    'tests/integration/test_meter_to_invoice.py',
    'tests/integration/test_outbox_and_events.py',
    'tests/e2e/test_core_flow.py',
    'tests/load/locustfile.py'
)

# Six FastAPI applications: 5 domain microservices + Auth.
# Alembic is scaffolded here (INI, env.py, script.py.mako, versions/).
# Only numbered migration revisions are generated LATER, after ORM models exist.
$serviceCommon = @(
    'Dockerfile',
    '.dockerignore',
    'requirements.txt',
    'alembic.ini',
    'migrations/README',
    'migrations/env.py',
    'migrations/script.py.mako',
    'migrations/versions/.gitkeep',
    'app/__init__.py',
    'app/main.py',
    'app/config.py',
    'app/db.py',
    'app/models.py',
    'app/schemas.py',
    'app/repository.py',
    'app/service.py',
    'app/api.py',
    'tests/conftest.py',
    'tests/test_api.py',
    'tests/test_service.py'
)

$serviceExtra = @{
    auth = @(
        'app/api_internal.py',      # JWT verification for Nginx auth_request
        'app/security.py'
    )
    room = @(
        'app/api_internal.py',
        'app/messaging.py',
        'app/worker.py'
    )
    tenant = @(
        'app/api_internal.py',
        'app/clients.py',           # Calls Room internal REST
        'app/messaging.py',
        'app/worker.py',
        'app/scheduler.py'
    )
    metering = @(
        'app/api_internal.py',
        'app/messaging.py',        # Domain events + telemetry through RabbitMQ
        'app/worker.py',
        'app/scheduler.py'
    )
    billing = @(
        'app/api_internal.py',
        'app/api_public.py',
        'app/api_webhook.py',
        'app/clients.py',          # Tenant and Metering internal REST
        'app/calculator.py',
        'app/momo.py',
        'app/messaging.py',
        'app/worker.py',
        'app/scheduler.py'
    )
    notification = @(
        'app/clients.py',          # Billing internal REST
        'app/messaging.py',
        'app/worker.py'
    )
}

$serviceNames = @('auth', 'room', 'tenant', 'metering', 'billing', 'notification')
$allFiles = New-Object 'System.Collections.Generic.List[string]'
foreach ($f in $rootFiles) { [void]$allFiles.Add($f) }
foreach ($name in $serviceNames) {
    $prefix = if ($name -eq 'auth') { 'backend/auth' } else { "backend/services/$name" }
    foreach ($relative in ($serviceCommon + $serviceExtra[$name])) {
        [void]$allFiles.Add("$prefix/$relative")
    }
}

# Fail before touching files if a path is duplicated or unsafe.
$duplicates = @($allFiles | Group-Object | Where-Object { $_.Count -gt 1 })
if ($duplicates.Count -gt 0) {
    throw ('Duplicate paths in manifest: ' + (($duplicates | ForEach-Object { $_.Name }) -join ', '))
}
foreach ($relative in $allFiles) {
    if ($relative.StartsWith('/') -or $relative.Contains('..') -or $relative.Contains(':')) {
        throw "Unsafe relative file path: $relative"
    }
}

# Non-empty starter contents for crucial foundational files.
# Business and infrastructure contracts are placeholders until reviewed.
$seed = @{}
$seed['.gitignore'] = @'
.env
.env.*
!.env.example
!.env.*.example
.venv/
venv/
__pycache__/
*.py[cod]
.pytest_cache/
.ruff_cache/
.mypy_cache/
.coverage
htmlcov/
node_modules/
dist/
build/
*.egg-info/
.terraform/
*.tfstate
*.tfstate.*
terraform.tfvars
*.log
.idea/
.vscode/
'@
$seed['.gitattributes'] = @'
*.sh text eol=lf
*.py text eol=lf
*.yaml text eol=lf
*.yml text eol=lf
*.mako text eol=lf
'@
$seed['.editorconfig'] = @'
root = true
[*]
charset = utf-8
end_of_line = lf
insert_final_newline = true
indent_style = space
indent_size = 4
[*.{yaml,yml}]
indent_size = 2
[*.md]
trim_trailing_whitespace = false
'@
$seed['.env.example'] = @'
# EXAMPLE ONLY. DO NOT COMMIT REAL SECRETS.
POSTGRES_USER=postgres
POSTGRES_PASSWORD=CHANGE_ME
RABBITMQ_DEFAULT_USER=admin
RABBITMQ_DEFAULT_PASS=CHANGE_ME
SERVICE_TOKEN=CHANGE_ME
JWT_SECRET=CHANGE_ME
OWNER_EMAIL=owner@example.com
# Each backend container receives its own DATABASE_URL for its logical DB.
# MoMo and Brevo credentials will be added when those integrations are implemented.
'@
$seed['README.md'] = @'
# Rental Management - Microservices

Five FastAPI business services (Room, Tenant, Metering, Billing, Notification),
FastAPI Auth, Nginx API Gateway, PostgreSQL (six logical DBs), RabbitMQ + MQTT,
Python IoT simulator, React frontend (not scaffolded here).

This scaffold creates the file layout, minimal FastAPI health endpoints,
Dockerfiles, and Alembic templates. It is NOT a running integrated system yet.
Fill contracts, infra configuration, business ORM models, and compose files next.
Run Alembic revision generation after ORM models are written.

Do not expose service/internal API ports, PostgreSQL, or RabbitMQ publicly.
'@
$seed['requirements-dev.txt'] = @'
pytest>=8,<10
pytest-asyncio>=0.24
httpx>=0.27,<1
ruff>=0.7
locust>=2,<4
PyYAML>=6,<7
'@
$seed['pyproject.toml'] = @'
[tool.pytest.ini_options]
testpaths = ["backend", "simulator/tests", "tests"]
addopts = "--import-mode=importlib"
asyncio_mode = "auto"

[tool.ruff]
line-length = 100
'@
$seed['infra/rabbitmq/enabled_plugins'] = '[rabbitmq_management,rabbitmq_mqtt].'
$seed['infra/k8s/README.md'] = 'Optional local kind demo. Create manifests only when the core Compose deployment works.'
$seed['docs/AI_MAP.md'] = @'
# AI Chat Context Map

Start with docs/SYSTEM_DESIGN.md and the relevant docs/services/<service>.md.
For a cross-service workflow, add docs/flows/<flow>.md.
Read only the necessary source modules and matching tests for the task.
Use contracts/openapi.yaml and contracts/asyncapi.yaml for external interfaces.
Never paste .env, secrets, database dumps, or access tokens into AI chat.
'@

$alembicIni = @'
[alembic]
script_location = migrations
prepend_sys_path = .
'@
$alembicEnv = @'
"""Alembic environment for one service-owned database.

Set DATABASE_URL before running Alembic from the service directory.
Populate app.models with SQLAlchemy ORM classes before autogenerating.
"""
import os

from alembic import context
from sqlalchemy import create_engine, pool

from app.db import Base
import app.models  # noqa: F401 - register ORM models for autogenerate

config = context.config
target_metadata = Base.metadata


def database_url() -> str:
    url = os.environ.get("DATABASE_URL")
    if not url:
        raise RuntimeError("DATABASE_URL is required for Alembic")
    return url


def run_migrations_offline() -> None:
    context.configure(
        url=database_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    engine = create_engine(database_url(), poolclass=pool.NullPool)
    with engine.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
        )
        with context.begin_transaction():
            context.run_migrations()
    engine.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
'@
$alembicRevision = @'
"""${message}

Revision ID: ${up_revision}
Revises: ${down_revision | comma,n}
Create Date: ${create_date}
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
${imports if imports else ""}

revision: str = ${repr(up_revision)}
down_revision: Union[str, None] = ${repr(down_revision)}
branch_labels: Union[str, Sequence[str], None] = ${repr(branch_labels)}
depends_on: Union[str, Sequence[str], None] = ${repr(depends_on)}


def upgrade() -> None:
    ${upgrades if upgrades else "pass"}


def downgrade() -> None:
    ${downgrades if downgrades else "pass"}
'@

$dockerfile = @'
FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY app/ ./app/
COPY alembic.ini ./
COPY migrations/ ./migrations/
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
'@
$dockerignore = @'
.env
.venv/
__pycache__/
*.pyc
.pytest_cache/
.ruff_cache/
tests/
'@
$pythonBase = @'
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass
'@
$requirementsCore = @'
fastapi>=0.115,<1
uvicorn[standard]>=0.30,<1
sqlalchemy>=2.0,<3
psycopg[binary]>=3.2,<4
alembic>=1.13,<2
pydantic-settings>=2,<3
'@
$requirementsHttp = "`nhttpx>=0.27,<1"
$requirementsAmqp = "`naio-pika>=9,<10"

foreach ($name in $serviceNames) {
    $prefix = if ($name -eq 'auth') { 'backend/auth' } else { "backend/services/$name" }
    $seed["$prefix/Dockerfile"] = $dockerfile
    $seed["$prefix/.dockerignore"] = $dockerignore
    $required = $requirementsCore
    if ($name -in @('tenant', 'billing', 'notification')) {
        $required += $requirementsHttp
    }
    if ($name -ne 'auth') {
        $required += $requirementsAmqp
    }
    if ($name -eq 'auth') {
        $required += "`nPyJWT>=2.9,<3`npwdlib[argon2]>=0.2,<1"
    }
    $seed["$prefix/requirements.txt"] = $required + "`n"
    $seed["$prefix/alembic.ini"] = $alembicIni
    $seed["$prefix/migrations/README"] = 'This folder belongs to one service. Generate revision files using alembic revision --autogenerate after the ORM is ready.'
    $seed["$prefix/migrations/env.py"] = $alembicEnv
    $seed["$prefix/migrations/script.py.mako"] = $alembicRevision
    $seed["$prefix/app/db.py"] = $pythonBase
    $seed["$prefix/app/models.py"] = "from app.db import Base`n`n# TODO: define service-owned ORM models here before running Alembic.`n"
    $seed["$prefix/app/main.py"] = @"
from fastapi import FastAPI

app = FastAPI(title="$name", version="0.1.0")


@app.get("/health", include_in_schema=False)
async def health() -> dict[str, str]:
    return {"status": "ok"}

# TODO: /ready must check the dependencies needed for serving requests.
# TODO: add routers after their API contracts and schemas are implemented.
"@
}

$seed['simulator/.dockerignore'] = $dockerignore
$seed['simulator/requirements.txt'] = @'
paho-mqtt>=2,<3
httpx>=0.27,<1
'@
$seed['simulator/Dockerfile'] = @'
FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY app/ ./app/
CMD ["python", "-m", "app.main"]
'@

# Create missing files; fill empty starter placeholders but never overwrite non-empty files.
$utf8NoBom = [System.Text.UTF8Encoding]::new($false)
foreach ($relative in $emptyDirectories) {
    $native = $relative.Replace('/', [System.IO.Path]::DirectorySeparatorChar)
    [void](New-Item -ItemType Directory -Path (Join-Path $root $native) -Force)
}

$created = 0
$existing = 0
$initialized = 0
foreach ($relative in $allFiles) {
    $native = $relative.Replace('/', [System.IO.Path]::DirectorySeparatorChar)
    $destination = Join-Path -Path $root -ChildPath $native
    $folder = Split-Path -Path $destination -Parent
    [void](New-Item -ItemType Directory -Path $folder -Force)
    if (Test-Path -LiteralPath $destination) {
        if (-not (Test-Path -LiteralPath $destination -PathType Leaf)) {
            throw "Expected file, but found directory: $relative"
        }
        # Useful when V2 previously made an empty Dockerfile / requirements file.
        if (((Get-Item -LiteralPath $destination).Length -eq 0) -and $seed.ContainsKey($relative)) {
            [System.IO.File]::WriteAllText($destination, [string]$seed[$relative], $utf8NoBom)
            $initialized++
        } else {
            $existing++
        }
        continue
    }
    $content = ''
    if ($seed.ContainsKey($relative)) { $content = [string]$seed[$relative] }
    [System.IO.File]::WriteAllText($destination, $content, $utf8NoBom)
    $created++
}

# Mandatory project structure assertions (fail immediately if incomplete).
$missing = @()
foreach ($relative in $allFiles) {
    $native = $relative.Replace('/', [System.IO.Path]::DirectorySeparatorChar)
    if (-not (Test-Path -LiteralPath (Join-Path $root $native) -PathType Leaf)) {
        $missing += $relative
    }
}
foreach ($relative in $emptyDirectories) {
    $native = $relative.Replace('/', [System.IO.Path]::DirectorySeparatorChar)
    if (-not (Test-Path -LiteralPath (Join-Path $root $native) -PathType Container)) {
        $missing += "$relative/"
    }
}
if ($missing.Count -gt 0) {
    throw ('Scaffold verification FAILED. Missing: ' + ($missing -join ', '))
}

Write-Host ''
Write-Host "Project root: $root" -ForegroundColor Cyan
Write-Host "Manifest check: PASS ($($allFiles.Count) files, $($emptyDirectories.Count) dedicated directories)" -ForegroundColor Green
Write-Host "New files: $created | Existing empty templates initialized: $initialized | Existing files preserved: $existing"
Write-Host 'Includes: Dockerfiles, requirements, Alembic scaffolds, Nginx, RabbitMQ, PostgreSQL, Terraform, CI/CD, tests, docs, and simulator.'
Write-Host 'frontend/ was created (no frontend files were generated).'
Write-Host 'No migration REVISION files were generated; create those only AFTER the 26 ORM models are defined.'
Write-Host 'IMPORTANT: Compose, Nginx, RabbitMQ topology, Terraform, and API contracts still need real configuration before deployment.'

# Rental Management (Cloud Microservices)

Backend: FastAPI Auth + 5 business services (Room, Tenant, Metering,
Billing, Notification), Nginx Gateway, PostgreSQL (six logical databases),
RabbitMQ/AMQP + MQTT, Mailpit. Frontend is a separate React/Vite workstream.

**Status:** Docker infrastructure, ORM and migrations exist; most business
routes, workers and schedulers are intentionally not implemented yet.
A green P00 smoke check is **not** an end-to-end business acceptance test.

## Start / stop on Windows (PowerShell 5.1)

Open Docker Desktop first. In the project root:

```powershell
docker compose -f compose.yaml -f compose.dev.yaml up -d --build
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\smoke_test.ps1
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\verify_schema_v3.ps1
```

The Compose file runs six `*-migrate` one-shot jobs **before** each application
becomes healthy. Both Room and Metering have previous revisions 002; Room now
also has 003. Do not edit already-applied migrations to update revisions.

Stop safely:

```powershell
docker compose stop
```

**Never run `docker compose down -v` on the local project:** it deletes the
PostgreSQL/RabbitMQ volumes. CI uses it only on an ephemeral GitHub runner.

## Demo seed (optional)

The seed is a deterministic **direct ORM snapshot**, not the runtime API flow.
It never creates fake successful MoMo payments or fake email-delivery events.

```powershell
# Seeds Auth (prompts for a local demo password) and all business DBs:
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\run_seed_demo.ps1

# Skip both creating AND verifying the demo Auth account:
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\run_seed_demo.ps1 -SkipAuth
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\verify_seed_demo.ps1 -SkipAuth
```

`run_seed_demo.ps1` verifies 6 Alembic heads before any inserts. It is
idempotent: running it again keeps existing deterministic rows. `-SkipAuth`
still validates Auth **schema**, but does not require an Auth demo account.

## GitHub Actions CI

`.github/workflows/ci.yml` runs checks for Python/YAML, seed tests, backend
unit tests as they are implemented, migrations, seed/constraints, and a **new
clean-stack smoke job**. Each CI job gets a separate new Ubuntu runner and
test-only `.env` file. `compose-startup-smoke` builds all services and runs
normal `docker compose up -d --build` on a clean project volume, then tests
six exit-0 migration jobs, RabbitMQ bootstrap, all healthchecks and Gateway
HTTP 200. This job never connects to the laptop's PostgreSQL.

Run the **read-only** smoke test against your already running local stack:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\smoke_test.ps1 -TimeoutSeconds 180
```

This command **does not** start, stop or reset containers. The first run of
`docker compose up -d --build` with the new migration must complete first.
The CI PostgreSQL/seed job also asserts the Room 003 hierarchy invariant.

## Hierarchy rule (room_v3_003)

After creation, `buildings.property_id` and `floors.building_id` are immutable,
including if a building/floor is still empty. Reparenting isn't a supported
business operation. This prevents a race condition between room creation
and moving its floor/building. `PATCH` of name and status is still possible.

## Git workflow

Create a branch for P00 (`fix/p00-ci-seed-hierarchy`), apply and test the
changes, commit/push, open a Pull Request and wait for the **two CI database /
Compose jobs** plus static/service jobs to complete successfully before merge.
Two empty CD workflow placeholders (`publish.yml` and `deploy.yml`) are
removed by the installer **only if they are zero bytes**. They are recreated
later during the AWS/GHCR deployment phase.

Do not commit `.env`, login passwords, MoMo secrets or other credentials.

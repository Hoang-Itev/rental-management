# P04: Tenant / DRAFT → SCHEDULED Contracts

## Boundary and data ownership

Tenant owns `tenant_db.tenants`, `contracts`, `contract_terms` and `contract_events`. Room owns `room_db.rooms`; **there is no cross-database FK**. Tenant calls Room at `GET http://room:8000/internal/v1/rooms/{room_id}/validation` with `X-Service-Token` from Docker Compose. A missing room yields 404; unresponsive/malformed Room yields 503; INACTIVE Room (or inactive parent property/building/floor) prevents confirmation with 409.

Public owner API `/api/v1/tenants` and `/api/v1/contracts` is protected by existing Nginx `auth_request` and JWT, not by tenant-login accounts. Only Nginx adds verified `X-Auth-User-Id`; Tenant does not expose Room or database credentials to browser clients. Private `GET /internal/v1/contracts/{id}` requires `X-Service-Token`, and Nginx blocks `/internal/` from the outside.

## Write workflow

`POST /api/v1/tenants` creates a payer profile. `POST /api/v1/contracts` requires `initial_terms`, validates that the referenced Room exists (INACTIVE is allowed at DRAFT stage), snapshots the room code, and atomically writes a DRAFT contract, its initial price term, and CREATED audit event.

The contract's `end_date` is **inclusive**, while price terms use `[effective_from, effective_to)` and `effective_to = null` means unbounded. New term versions are append-only while DRAFT; adding a version automatically closes the preceding term at the new effective date, prohibiting overlaps and gaps. `POST /api/v1/contracts/{id}/confirm` locks the contract row, requires a payer email, full term coverage and no overlapping confirmed contract, performs Room REST validation, changes status to `SCHEDULED` and writes one CONFIRMED audit event in the same local transaction. Repeated confirmation returns the existing SCHEDULED contract without a second CONFIRMED event.

PostgreSQL `ex_contracts_room_period` is the authoritative concurrency gate for SCHEDULED, ACTIVE and EXPIRED_PENDING with inclusive contract end date, even if simultaneous confirmations pass an application-level pre-check. Any constraint violation becomes HTTP 409; the operation rolls back. Date validation is performed both by DTO and DB constraints. DRAFT contracts do not block each other.

P04 **does not** activate contracts, occupy rooms, publish `ContractStarted`, schedule jobs, send email or charge invoices. Those are separate later stages. A room becoming INACTIVE after confirmation cannot be prevented atomically across databases; the future activation workflow must revalidate the room before transitioning to ACTIVE.

The V3 schema contains a legacy optional `deposit_amount` column, but P04 does not expose or use deposits. No migration needed.

## Supported public routes

`GET/POST /api/v1/tenants`, `GET/PATCH /api/v1/tenants/{id}`. `GET/POST /api/v1/contracts`, `GET/PATCH /api/v1/contracts/{id}`, `GET/POST /api/v1/contracts/{id}/terms`, `GET /api/v1/contracts/{id}/events`, `POST /api/v1/contracts/{id}/confirm`. List responses use `{items, meta}` as required by `contracts/openapi.yaml`. Operations `renew/end/cancel/expiring/jobs` are **not implemented** in P04 despite being reserved in the wider OpenAPI design.

## Tests

`./scripts/test_p04_unit.ps1` validates SQLite-backed Tenant service/API and mocked Room HTTP behavior, requiring ≥80% coverage on `app.service`. The SQLite harness removes PostgreSQL-only GiST exclusion constraints: it does NOT claim to test database locking.

`./scripts/test_p04_integration.ps1` provisions a randomized disposable Docker Compose project with PostgreSQL and RabbitMQ, applies **real** Room and Tenant migrations, starts both services, and exercises HTTP flows across them. It covers term versioning, inclusive overlap prevention, inactive rooms and **two concurrent confirm requests** against the real PostgreSQL exclusion constraint. It removes only the disposable project and its two volumes, never the user's running rental-management stack.

`./scripts/test_p04_gateway.ps1` is optional after the Tenant container is rebuilt. It uses existing owner credentials and Nginx to exercise the full flow. **It creates permanent demo records in the local dev databases** and does not auto-delete them.

## Constraints and caveats

At-least-once `RoomCreated` (P03) is not modified. Confirming SCHEDULED in P04 does not create any new event to RabbitMQ. Email is required for the representative payer at confirmation so future invoice emails have a target. Room REST uses a bounded 3-second timeout and deliberately fails closed. No distributed transactions are attempted.

Unit and real integration coverage are separate gates; a local test success does not establish GitHub CI success. Do not merge until all checks are green.

# P05 Contract lifecycle: design and acceptance

## Scope

The Tenant service owns business contract status and `tenant_db`. Room owns the **physical occupancy projection** in `room_db`; Metering owns physical meter readings and handover cutoffs in `metering_db`. There is no cross-database transaction. Domain events use the existing durable `rental.domain.v1` topic exchange.

Transitions: `DRAFT -> SCHEDULED` (P04); `SCHEDULED -> ACTIVE` via due scheduler; `ACTIVE -> EXPIRED_PENDING` after the **inclusive** planned end day; and `ACTIVE/EXPIRED_PENDING -> ENDED` by owner confirmation of actual handover. `EXPIRED_PENDING` does **not** free the room and emits no `ContractEnded`. A renewal extends end_date and can add a new pricing version at the exact next-day boundary, while PostgreSQL GiST EXCLUDE is still authoritative for planned period overlap.

The owner is the only user account. Internal Room validation uses `X-Service-Token`. Tenant activation checks both (1) another `ACTIVE/EXPIRED_PENDING` contract in Tenant database and (2) Room's `occupancy_contract_id`. When Room has not yet consumed the previous ContractEnded, activation remains SCHEDULED and the scheduler retries. **This is eventually consistent**, not an atomic distributed lock. Room consumer additionally orders projection by effective_at.

## Effective_at semantics

`ContractStarted`: 00:00 `start_date` in `Asia/Ho_Chi_Minh`.

`ContractEnded`: 00:00 **the next day after** `actual_end_date` in `Asia/Ho_Chi_Minh`. The last occupied day is inclusive. If an owner confirms a handover for the current date, the end event remains in Tenant Outbox until the next local midnight. The public demo `as_of` parameter cannot be set in the future. The scheduler does not activate a contract outside its planned period.

The Tenant Outbox SQL filters rows whose `effective_at <= NOW()`; broker confirms precede the `published_at` update. Retries yield **at-least-once**, not exactly-once transport. Room and Metering record `processed_events` in the same local transaction as business effects. Future events arriving externally are **deferred** to broker TTL retry without exhausting the poison-message retry budget. Non-future exceptions use TTL retry then DLQ.

## Deterministic same-instant handover

`ContractEnded(A)` then `ContractStarted(B)` or the reverse both converge to B's occupancy if both share the same effective_at. Room only clears occupancy for a matching contract ID. A late old start event is discarded using the stored `occupancy_updated_at`, under `SELECT FOR UPDATE` on the room row.

Metering's V3 schema has a unique *physical* cutoff for a meter at a timestamp. P05 adds `meter_cutoff_reasons`, which lets one cutoff map to both `CONTRACT_END(A)` and `CONTRACT_START(B)`. The canonical `meter_cutoffs.cutoff_type` uses `CONTRACT_START` when both exist. **Future Billing code must inspect `meter_cutoff_reasons` for both obligations** and not infer the two contract associations from the single `meter_cutoffs.contract_id` field.

No sensor readings may be invented. When telemetry is absent, a handover cutoff is PENDING with NULL reading, requiring later confirmation or manual entry in subsequent Metering work.

## Why migrations are necessary

`tenant_v3_002` relaxes `actual_end_date <= end_date`. Otherwise late physical handover after a planned end can never be represented honestly. It retains `actual_end_date >= start_date`.

`metering_v3_003` adds the logical handover reasons, preserving both business actors when cutoff timestamps coincide. No V3 tables are deleted.

## Tests

Room unit tests cover both orders, duplicates, stale and premature messages, safe ACK/retry/DLQ. Tenant tests cover time guard, physical occupancy, renew and actual late handover. Metering tests cover both orders, two meters, one physical cutoff each, two logical reasons each, future boundary deferral. Dedicated disposable Docker integration performs real HTTP against Room/Tenant, RabbitMQ publisher/consumer and three PostgreSQL logical databases. The local Gateway smoke test persists a demo tree and MUST NOT run on production.

## Operating

Start the API and lifecycle workers with `docker compose -f compose.yaml -f compose.workers.yaml up -d --build --wait`.

# P06 | MQTT Simulator → Metering

## Architecture

Simulator runs as an independent container in the `simulator` Docker profile. It calls the service-token-protected `GET /internal/v1/meters?status=ACTIVE&page=...&page_size=100`, then publishes cumulative readings over MQTT QoS 1 to `meters/{meter_id}/reading`. RabbitMQ's MQTT plugin bridges the topic to the existing durable `amq.topic` exchange with AMQP routing key `meters.{meter_id}.reading`. `metering.telemetry.q` is already bound to `meters.*.reading`; a separate `metering-telemetry-consumer` runs `python -m app.worker telemetry` and stores the reading in `metering_db`. Existing P03/P05 RoomCreated/ContractStarted/ContractEnded consumer continues with `python -m app.worker`.

MQTT JSON body: `meter_id` (UUID), `measured_at` (aware ISO8601 UTC), `reading_value` (nonnegative cumulative Decimal, at most three fractional places). Consumer verifies topic UUID equals payload UUID and rejects timestamps >5 minutes ahead. Simulation accelerates *consumption* only, never event time. `SIM_EPOCH` plus stable per-meter rate ensures no counter reset on Simulator restart; do not change epoch, rates, or scale mid-project if you want monotone measurements.

## Database semantics

No new migration: `meter_readings` already has PK `(meter_id, measured_at)` and `meter_alerts` supports `CONFLICTING_DUPLICATE` and `READING_DECREASE`; P05 `metering_v3_003` is already on main. The overall total stays 27 business tables. Consumer locks `meters` row (SELECT FOR UPDATE) to serialize concurrent telemetry. Identical duplicate -> ACK without insert. Same key, differing value -> original is preserved and **one** CONFLICTING_DUPLICATE alert is recorded. Out-of-order timestamps are compared to nearest VALID neighbours, not reception order. Consistent late reading -> VALID; value contradicting an earlier/later VALID neighbour -> SUSPECT with READING_DECREASE alert, preserving raw evidence. Billing should subsequently use confirmed/validated readings only.

RabbitMQ manual ACK happens **after DB commit**, or after publisher-confirmed transfer to a TTL retry queue or DLQ. Operational failures retry after 10/60/300 seconds and then enter DLQ. Invalid payload/topic, unknown or inactive meter -> DLQ. Retried messages retain `x-p06-original-key` because RabbitMQ's default-exchange TTL routing overwrites the delivered routing key. Delivery is at-least-once; natural-key idempotence, not exactly-once transport.

## Endpoints and deployment

Owner JWT read endpoints: `GET /api/v1/meters/{meter_id}/readings` (pagination, `from`/`to` aware timestamps), `GET /api/v1/meter-alerts` (status, alert_type, pagination), and convenience `GET /api/v1/meters/{meter_id}/alerts`. Nginx already routes these paths to Metering. Internal meter listing is service-token-only, not public.

Merge Compose files in order: `compose.yaml`, `compose.p03.yaml`, `compose.p05.yaml`, `compose.p06.yaml`. New P06 service is `metering-telemetry-consumer`. Simulator remains opt-in via `--profile simulator`. Settings: `SIM_INTERVAL_SECONDS=300`, `SIM_REFRESH_SECONDS=300`, `SIM_EPOCH=2026-01-01T00:00:00+00:00`, `SIM_TIME_SCALE=1`, `SIM_KWH_PER_DAY=4`, `SIM_M3_PER_DAY=0.5`.

## Testing and limits

`test_p06_unit.ps1` exercises P03/P05 unit regression plus P06 service/API/AMQP and Simulator. `test_p06_integration.ps1` runs a random disposable Compose project: real PostgreSQL migration head, two real meter rows, Simulator `--once` over real MQTT QoS1, AMQP consumer, persisted readings, repeat/mismatch and out-of-order alerts. CI adds `mqtt-metering-integration` with the same test script. `test_p06_gateway.ps1` is a separate read-only owner login + Nginx smoke for local stack. The authoring environment has no Docker/PowerShell; do not merge until Docker E2E and CI are green.

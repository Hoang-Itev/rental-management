# P08: Billing calculator (pure calculation only)

The calculator accepts **snapshots**, not direct access to `tenant_db` or `metering_db`. P09 will query services, check confirmed cutoff versions, construct snapshots, persist `invoice_items`, and issue invoices. This phase does not create or issue invoices or alter the database.

## Contract and rounding

Every time range is half-open `[start, end)` in Vietnam-local calendar dates. The contract's final *inclusive* day must be translated to the next exclusive date by the caller. Month boundaries use the actual Gregorian month length (including leap February).

Rent and **monthly service fee** are both prorated by occupied calendar days: `monthly_price × billed_days / calendar_days_in_month`. Each separate `(term, calendar month)` creates a line. For each line, the raw Decimal result is rounded to **integer VND using ROUND_HALF_UP**, never binary float or Python's banker-rounding. A daily unit price shown in `invoice_items.unit_price` is a **4-decimal display snapshot**, not the authority for recalculating `amount`; the original monthly integer rate remains the calculation source. Total is the sum of *rounded* line amounts, not one global rounded sum. This service-fee proration policy is an explicit P08 choice; it can be revised if the business rules require a non-prorated fixed service charge.

## Electricity/water and changing prices

One or more `UsageSnapshot` intervals for **each meter type** must exactly cover the invoice period, with no gaps, overlap or discontinuity. Each snapshot carries confirmed cutoff IDs, cumulative start/end values, and the meter ID. Consumption is `end_reading - start_reading`. Negative consumption is rejected; nothing is silently clamped to zero. Amount is `ROUND_HALF_UP(consumption × the contract-term unit price)` per segment. Meter readings support at most 3 decimals; stored unit prices show 4 decimals.

Contract term versions use the Tenant `contract_terms` effective interval `[effective_from, effective_to)`. Rent/service are segmented automatically by those dates. For electricity/water, **a price change inside the usage period requires an additional confirmed meter cutoff at that boundary**. Without it, the calculator rejects the interval (`PRICE_BOUNDARY_READING_REQUIRED`) rather than allocating unknown consumption proportionally across different rates. Both meters are required; missing or non-confirmed cutoffs are invalid. A later revision of a confirmed cutoff can only affect a new invoice snapshot; previous paid invoices must never be recomputed in place.

## Scope

P08 exports `app.calculator.calculate_invoice(...)`, `app.service.BillingCalculatorService.calculate(...)` and Pydantic snapshot types. `CalculationError.code` may be mapped to a blocked draft reason during P09. There are no new public endpoints, migrations, background schedulers, RabbitMQ events or changes to seed data in this phase.

Run the tests from `backend/services/billing` with:

`python -m pytest tests/test_service.py -q --cov=app.calculator --cov-report=term-missing --cov-fail-under=80`

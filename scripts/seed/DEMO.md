# Demo seed: reset local, load, then start workers

This profile is for disposable local demo data only. It keeps the baseline CI fixture unchanged.
The existing command `scripts/run_seed_demo.ps1 -UseDemoPassword` now selects presentation data.
No application business logic, OpenAPI or workflow files are changed.

## Pull the branch

Commit or stash your own changes first. Do not overwrite your local `.env`.

```powershell
cd "C:\Users\hoang\Documents\learn-space\cloud\rental-management"
git fetch origin
git switch feat/demo-overdue-seed
git pull --ff-only origin feat/demo-overdue-seed
```

## Reset only this project's local data

The next command deletes **all local PostgreSQL data, RabbitMQ messages and uploaded attachments**
for the Compose project `rental-management`. Mailpit mail disappears with its container too.
It preserves local `.env`, source files and Docker images; it does not touch other Docker projects.
Run only when you want to discard the old demo data.

```powershell
docker compose -p rental-management -f compose.yaml -f compose.workers.yaml --profile simulator down --volumes --remove-orphans
if ($LASTEXITCODE -ne 0) { throw 'Docker reset failed. Stop here.' }
Remove-Item -LiteralPath .seed-demo-date -ErrorAction SilentlyContinue
```

## Build and initialize the empty databases

Build once to match the source you pulled. No cache purge is necessary.
Seed scripts are bind-mounted; later edits to only seed files do not require an image rebuild.

```powershell
docker compose -f compose.yaml -f compose.workers.yaml --profile simulator build auth room tenant metering billing notification simulator nginx
if ($LASTEXITCODE -ne 0) { throw 'Build failed. Stop here.' }

docker compose -f compose.yaml up -d --wait postgres rabbitmq mailpit
if ($LASTEXITCODE -ne 0) { throw 'Infrastructure failed. Stop here.' }

powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\migrate_all_v3.ps1 -SkipBuild
if ($LASTEXITCODE -ne 0) { throw 'Migration failed. Stop here.' }
```

Do not start schedulers, consumers or simulator before loading and verifying seed data.
The seed runner refuses to run while those background services are running.

## Load presentation data and queue reminders

Keep `OWNER_EMAIL=hoangdv955@gmail.com` in `.env`. The demo login password is `123456789011`.

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\run_seed_demo.ps1 -UseDemoPassword
if ($LASTEXITCODE -ne 0) { throw 'Seed failed. Do not start workers yet.' }
```

The runner saves today's local date in ignored file `.seed-demo-date`. All services use that same date.
Rerunning before runtime demo activity retains deterministic rows; it does not reset paid invoices or change passwords.
To start a fresh rehearsal, repeat the reset/load procedure, including removing `.seed-demo-date`.
Baseline automated fixtures remain available with `-Profile baseline` on a separate empty test database.

After all six databases pass verification, the runner queues **12 real InvoiceReminderRequested events**
through Billing's normal `enqueue_reminder()` function, even before 09:00.
It does not insert fake payment attempts, SENT email jobs or public access tokens.
The regular workers create the jobs, request secure links and send mail once started.
Each invoice has its own reminder/link; the same invoice/day is deduplicated.

## Start everything

```powershell
docker compose -f compose.yaml -f compose.workers.yaml --profile simulator up -d --wait
if ($LASTEXITCODE -ne 0) { throw 'Runtime startup failed.' }

powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\smoke_test.ps1 -Runtime
```

Open the FE at http://localhost:8080 and Mailpit at http://localhost:8025.
Mailpit captures mail; using real recipient addresses does **not** make it deliver to Gmail/student inboxes.
For actual delivery keep your working external SMTP configuration in `.env`; no SMTP code changes are needed.
Check that `PUBLIC_BASE_URL` opens the frontend from the recipient's browser (localhost only works on your own machine).
Keep the working SePay sandbox/IPN settings; the seed does not alter them.

## What is ready to demo?

| Recipient | Overdue, unpaid invoices (one per room) |
|---|---|
| n23dccn089@student.ptithcm.edu.vn | A101, A105, A204 |
| n23dccn086@student.ptithcm.edu.vn | A102, A201, A205 |
| n23dccn090@student.ptithcm.edu.vn | A103, A202, B101 |
| hoangdv955@gmail.com | A104, A203, B102 |

All 12 are ISSUED, have positive totals and no payment attempts. Every email has three independent invoices.
Rent/service/electricity/water lines use the real Billing calculator. Invoices were issued 11 days before the pinned
seed date, with a 10-day payment deadline, so their deadline was yesterday.
The billed month is the most recent full month ending before that historical issue date.

| Scenario | Data and action |
|---|---|
| Overdue mail → SePay → receipt | Start with any of the 12 rooms above. Open its reminder email and pay through the existing sandbox flow. |
| Missing cutoff → manual confirmation → issue | B103 and B104 have periodic DRAFT invoices, with both end cutoffs PENDING. Confirm electricity/water first, then issue. New issuance gets a new 10-day deadline. |
| Final invoice | B105 is handed over/ENDED with a FINAL DRAFT. Confirm both CONTRACT_END cutoffs, then issue. The period is not covered by any other invoice. |
| Contract expiry email | B201 is ACTIVE and ends five days after the pinned date. Tenant scheduler normally checks expiry mail from 09:00 Vietnam time. |
| New tenant/contract | B202–B205 are free. Two additional tenant profiles are available. |
| MQTT readings | 40 meters have monotone historical samples. Simulator continues from Metering's baseline when runtime starts. |

For B103/B104 monthly cutoff confirmation: end electricity = start electricity + (72 + room_index*3);
end water = start water + (8 + room_index), where room_index is zero-based in the room list.
For B105 use a reading consistent with neighboring samples; an earlier sample does not justify arbitrary decreases.
The seed's exact recommended values and IDs can be printed without changing the DB:

```powershell
$env:SEED_PROFILE = 'presentation'
$env:SEED_AS_OF = (Get-Content .seed-demo-date -Raw).Trim()
try {
    docker compose -f compose.yaml -f infra/compose/seed.yaml run --rm --no-deps metering python /seed/presentation.py
} finally {
    Remove-Item Env:SEED_PROFILE, Env:SEED_AS_OF -ErrorAction SilentlyContinue
}
```

To observe readings faster, set `SIM_INTERVAL_SECONDS=10` and `SIM_REFRESH_SECONDS=10` in `.env`,
then recreate only simulator. Do not change the host date or simulator time scale for monthly billing.

If no mail arrives, inspect:

```powershell
docker compose -f compose.yaml -f compose.workers.yaml logs --since 10m --tail 100 billing-outbox notification-worker
```

## Important rehearsal behavior

The pristine seed verification intentionally checks unpaid/DRAFT fixture states. After payment or issuing a DRAFT,
those checks no longer describe runtime data; use the UI and smoke test instead.
Clicking “remind” again today does not send another mail for an invoice already reminded today.
Choose another unpaid invoice to show another reminder. Never delete dedupe records or fake PAID state to force a demo.
Mail is processed asynchronously; if external SMTP rejects a destination the existing retry/FAILED handling applies.

#!/usr/bin/env bash
# Linux counterpart of run_seed_demo.ps1. Seed snapshots before starting workers.
set -euo pipefail
umask 077

cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.."
cloud=false
demo_password=false
for option in "$@"; do
  case "$option" in
    --cloud) cloud=true ;;
    --use-demo-password) demo_password=true ;;
    *) echo "Usage: bash scripts/run_seed_demo.sh [--cloud] [--use-demo-password]" >&2; exit 1 ;;
  esac
done
[[ -f .env ]] || { echo '.env missing. Configure the environment first.' >&2; exit 1; }

export SEED_MODE=demo SEED_PROFILE=presentation
trap 'unset SEED_MODE SEED_PROFILE SEED_AS_OF SEED_OWNER_PASSWORD' EXIT
if [[ ! -f .seed-demo-date ]]; then
  TZ=Asia/Ho_Chi_Minh date +%F > .seed-demo-date
fi
export SEED_AS_OF
SEED_AS_OF=$(tr -d '\r\n' < .seed-demo-date)
[[ "$SEED_AS_OF" =~ ^[0-9]{4}-[0-9]{2}-[0-9]{2}$ ]] || { echo 'Invalid .seed-demo-date' >&2; exit 1; }

compose=(docker compose -f compose.yaml -f compose.workers.yaml)
if "$cloud"; then compose+=(-f compose.prod.yaml); fi
compose+=(-f infra/compose/seed.yaml)
"${compose[@]}" config --quiet
running=$("${compose[@]}" --profile simulator ps --status running --services)
while IFS= read -r service; do
  case "$service" in
    *outbox*|*consumer*|*scheduler*|notification-worker|simulator)
      echo "Stop background service before seeding: $service" >&2; exit 1 ;;
  esac
done <<< "$running"

if "$demo_password"; then
  SEED_OWNER_PASSWORD=123456789011
else
  read -rsp 'Set owner password (at least 12 characters): ' SEED_OWNER_PASSWORD
  echo
fi
(( ${#SEED_OWNER_PASSWORD} >= 12 )) || { echo 'Password must have at least 12 characters.' >&2; exit 1; }
export SEED_OWNER_PASSWORD

for service in auth room tenant metering billing notification; do
  echo "Seeding: $service"
  "${compose[@]}" run --rm --no-deps "$service" python /seed/seed_service.py "$service"
done
for service in auth room tenant metering billing notification; do
  echo "Verifying: $service"
  "${compose[@]}" run --rm --no-deps "$service" python /seed/verify_service.py "$service"
done
"${compose[@]}" run --rm --no-deps billing python /seed/seed_service.py billing --queue-reminders
printf 'SEED DEMO OK: presentation data for %s; reminders queued.\n' "$SEED_AS_OF"

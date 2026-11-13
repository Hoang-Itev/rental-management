"""Demo snapshot seed for Database Design V3.

Run ONLY on disposable local/CI databases after Alembic migrations.
Unlike normal runtime commands this writes service-owned ORM tables directly:
no API handlers, outbox messages, payment confirmation or email dispatch.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import uuid
from datetime import date, datetime, timezone, timedelta
from decimal import Decimal
from pathlib import Path

# Docker service images use WORKDIR /app; script is mounted under /seed.
sys.path.insert(0, "/app")

DATA_FILE = Path(__file__).with_name("demo_data.json")
SEED_NAMESPACE = uuid.UUID("ba42fda9-1d5e-49e0-91b1-e123f5c139bb")
VN = timezone(timedelta(hours=7))
VALID_SERVICES = ("auth", "room", "tenant", "metering", "billing", "notification")
DATABASES = {s: f"{s}_db" for s in VALID_SERVICES}


def sid(kind: str, key: str) -> uuid.UUID:
    return uuid.uuid5(SEED_NAMESPACE, f"rental-demo-v1:{kind}:{key}")


def midnight_vn(day: str) -> datetime:
    return datetime.combine(date.fromisoformat(day), datetime.min.time(), tzinfo=VN).astimezone(timezone.utc)


def dataset() -> dict:
    return json.loads(DATA_FILE.read_text(encoding="utf-8"))


def money_for_room(room_code: str, data: dict) -> int:
    index = data["rooms"].index(room_code)
    return 2_500_000 + index * 100_000


def initial_meter_value(room_code: str, meter_type: str, data: dict) -> Decimal:
    index = data["rooms"].index(room_code)
    return Decimal(1000 + index * 130 if meter_type == "ELECTRICITY" else 50 + index * 7).quantize(Decimal("0.001"))


def delta_meter_value(room_code: str, meter_type: str, data: dict) -> Decimal:
    index = data["rooms"].index(room_code)
    return Decimal(72 + index * 3 if meter_type == "ELECTRICITY" else 8 + index).quantize(Decimal("0.001"))


def add_if_missing(session, model, **fields) -> bool:
    """Stable UUID, insert-only; no overwrite of existing rows."""
    obj_id = fields["id"]
    if session.get(model, obj_id) is not None:
        return False
    session.add(model(**fields))
    session.flush()  # immediately verify FK/check/unique constraints
    return True


def seed_auth(session, m, d: dict) -> int:
    from pwdlib import PasswordHash

    email = os.environ.get("OWNER_EMAIL", "").strip().lower()
    password = os.environ.get("SEED_OWNER_PASSWORD", "")
    if not email or "@" not in email or len(password) < 12:
        raise RuntimeError("OWNER_EMAIL and SEED_OWNER_PASSWORD (at least 12 characters) are required")
    # Never replace a pre-existing login or reset its password.
    return int(add_if_missing(
        session, m.User, id=sid("owner", email), email=email,
        full_name="Chủ trọ Demo", password_hash=PasswordHash.recommended().hash(password),
        is_active=True,
    ))


def seed_room(session, m, d: dict) -> int:
    n=0
    prop_id=sid("property", d["property"]["code"])
    n+=add_if_missing(session,m.Property,id=prop_id,name=d["property"]["name"],address=d["property"]["address"],description="Dữ liệu demo V3",status="ACTIVE")
    for b in d["buildings"]:
        b_id=sid("building", b["code"])
        n+=add_if_missing(session,m.Building,id=b_id,property_id=prop_id,name=b["name"],status="ACTIVE")
        for floor_no in (1,2):
            f_id=sid("floor",f"{b['code']}{floor_no}")
            n+=add_if_missing(session,m.Floor,id=f_id,building_id=b_id,floor_number=floor_no,name=f"Tầng {floor_no}",status="ACTIVE")
    for code in d["rooms"]:
        c=next((c for c in d["contracts"] if c["room_code"]==code),None)
        n+=add_if_missing(
            session,m.Room,id=sid("room",code),property_id=prop_id,
            floor_id=sid("floor",code[:2]),room_code=code,
            area_m2=Decimal("22.00"),listed_rent=money_for_room(code,d),status="ACTIVE",
            occupancy_contract_id=sid("contract",c["code"]) if c else None,
            occupancy_updated_at=midnight_vn(c["start_date"]) if c else None,
        )
    return n


def seed_tenant(session,m,d:dict)->int:
    n=0
    for i,t in enumerate(d["tenants"]):
        n+=add_if_missing(session,m.Tenant,id=sid("tenant",str(i)),full_name=t["name"],email=t["email"],phone=None,note="Hồ sơ minh họa")
    for c in d["contracts"]:
        i=c["tenant_index"]
        cid=sid("contract",c["code"])
        n+=add_if_missing(session,m.Contract,id=cid,contract_code=c["code"],room_id=sid("room",c["room_code"]),
            room_code_snapshot=c["room_code"],representative_tenant_id=sid("tenant",str(i)),
            start_date=date.fromisoformat(c["start_date"]),end_date=date.fromisoformat(c["end_date"]),
            status="ACTIVE",deposit_amount=money_for_room(c["room_code"],d))
        n+=add_if_missing(session,m.ContractTerm,id=sid("term",c["code"]),contract_id=cid,
            effective_from=date.fromisoformat(c["start_date"]),effective_to=None,
            monthly_rent=money_for_room(c["room_code"],d),
            electricity_unit_price=3500,water_unit_price=15000,monthly_service_fee=100000)
        for evt,day in (("CREATED","2026-08-15"),("CONFIRMED","2026-08-20"),("STARTED",c["start_date"])):
            n+=add_if_missing(session,m.ContractEvent,id=sid("contract_event",f"{c['code']}:{evt}"),
                contract_id=cid,event_type=evt,occurred_at=midnight_vn(day),details={"seed_demo":True})
    return n


def seed_metering(session,m,d:dict)->int:
    n=0
    for code in d["rooms"]:
        for kind,unit in (("ELECTRICITY","KWH"),("WATER","M3")):
            mid=sid("meter",f"{code}:{kind}")
            base=initial_meter_value(code,kind,d)
            delta=delta_meter_value(code,kind,d)
            blocked=code in d["blocked_rooms"]
            n+=add_if_missing(session,m.Meter,id=mid,room_id=sid("room",code),
                meter_code=f"DEMO-{code}-{kind[0]}",meter_type=kind,unit=unit,
                initial_reading=base,status="ACTIVE")
            series=[("2026-10-01",base),("2026-10-15",base+delta/2)]
            if not blocked:
                series.append(("2026-11-01",base+delta))
            for day,val in series:
                timestamp=midnight_vn(day)
                # meter_readings has a COMPOSITE primary key, not a UUID id.
                pk={"meter_id":mid,"measured_at":timestamp}
                if session.get(m.MeterReading,pk) is None:
                    session.add(m.MeterReading(meter_id=mid,measured_at=timestamp,
                        reading_value=val,validation_status="VALID",received_at=timestamp))
                    session.flush()
                    n+=1
            for day,val,pending in (("2026-10-01",base,False),("2026-11-01",base+delta,blocked)):
                n+=add_if_missing(session,m.MeterCutoff,id=sid("cutoff",f"{code}:{kind}:{day}"),
                    meter_id=mid,contract_id=None,cutoff_type="MONTHLY",cutoff_at=midnight_vn(day),
                    reading_value=None if pending else val,source="AUTOMATIC",
                    source_reading_at=None if pending else midnight_vn(day),
                    status="PENDING" if pending else "CONFIRMED",
                    confirmed_at=None if pending else midnight_vn(day))
    return n


def seed_billing(session, m, d: dict) -> int:
    """Use the production Billing calculator so demo line items cannot drift."""
    from app.calculator import calculate_invoice
    from app.schemas import InvoiceCalculationInput, TermSnapshot, UsageSnapshot

    n = 0
    period_start = date.fromisoformat(d["billing_month"])
    period_end = date.fromisoformat(d["period_end"])
    due = date.fromisoformat(d["invoice_due_date"])
    # The demo invoice is issued on the second day of the month after its period.
    issued_day = period_end + timedelta(days=1)
    if due != issued_day.replace(day=5):
        raise RuntimeError("Demo invoice due date must be day 5 of the issue month")

    for contract in d["contracts"]:
        room_code = contract["room_code"]
        blocked = room_code in d["blocked_rooms"]
        invoice_id = sid("invoice", contract["code"])
        contract_id = sid("contract", contract["code"])
        term_id = sid("term", contract["code"])
        tenant = d["tenants"][contract["tenant_index"]]
        lines = []
        amount = 0

        if not blocked:
            term = TermSnapshot(
                id=term_id, effective_from=date.fromisoformat(contract["start_date"]),
                effective_to=None, monthly_rent=money_for_room(room_code, d),
                electricity_unit_price=3500, water_unit_price=15000,
                monthly_service_fee=100000,
            )
            usage_segments = []
            for meter_type in ("ELECTRICITY", "WATER"):
                base = initial_meter_value(room_code, meter_type, d)
                usage_segments.append(UsageSnapshot(
                    meter_type=meter_type,
                    meter_id=sid("meter", f"{room_code}:{meter_type}"),
                    period_start=period_start, period_end=period_end,
                    source_cutoff_start_id=sid("cutoff", f"{room_code}:{meter_type}:{period_start.isoformat()}"),
                    source_cutoff_end_id=sid("cutoff", f"{room_code}:{meter_type}:{period_end.isoformat()}"),
                    start_cutoff_status="CONFIRMED", end_cutoff_status="CONFIRMED",
                    start_reading=base,
                    end_reading=base + delta_meter_value(room_code, meter_type, d),
                ))
            result = calculate_invoice(InvoiceCalculationInput(
                period_start=period_start, period_end=period_end,
                terms=[term], usage_segments=usage_segments,
            ))
            lines = result.items
            amount = result.total_amount

        n += add_if_missing(
            session, m.Invoice, id=invoice_id,
            invoice_code=f"DEMO-INV-{room_code}-{period_start:%Y%m}",
            contract_id=contract_id, room_id=sid("room", room_code),
            invoice_type="PERIODIC", billing_month=period_start,
            period_start=period_start, period_end=period_end,
            status="DRAFT" if blocked else "ISSUED",
            blocked_reason="PENDING_CUTOFF" if blocked else None,
            revision=1, total_amount=amount, due_date=due,
            issued_at=None if blocked else midnight_vn(issued_day.isoformat()),
            tenant_name_snapshot=tenant["name"],
            tenant_email_snapshot=tenant["email"], room_code_snapshot=room_code,
        )
        for j, line in enumerate(lines):
            n += add_if_missing(
                session, m.InvoiceItem,
                id=sid("invoice_item", f"{contract['code']}:{j}"),
                invoice_id=invoice_id, **line.model_dump(),
            )
    return n


def seed_notification(session,m,d:dict)->int:
    # No invented InvoiceIssued/PaymentSucceeded message or fabricated 'SENT' emails.
    # Notification jobs will be created from real events when worker is implemented.
    return 0


def safety_check(service:str):
    if os.getenv("SEED_MODE") != "demo":
        raise RuntimeError("Refusing seed: SEED_MODE=demo required (use run_seed_demo.ps1)")
    from sqlalchemy.engine import make_url
    url = make_url(os.environ.get("DATABASE_URL", ""))
    if url.host != "postgres" or url.database != DATABASES[service]:
        raise RuntimeError("Refusing seed: expected Docker network host 'postgres' and service-owned database")


def main() -> int:
    parser=argparse.ArgumentParser()
    parser.add_argument("service",choices=VALID_SERVICES)
    parser.add_argument("--expect-existing", action="store_true", help="Fail if any new seed rows were inserted")
    args=parser.parse_args()
    safety_check(args.service)
    d=dataset()
    if len(d["rooms"])!=12 or len(d["contracts"])!=6:
        raise RuntimeError("Demo fixture inventory invalid")
    from app import models as m
    from app.db import get_sessionmaker
    funcs={
       "auth":seed_auth,"room":seed_room,"tenant":seed_tenant,
       "metering":seed_metering,"billing":seed_billing,"notification":seed_notification,
    }
    with get_sessionmaker()() as session:
        with session.begin():
            created=funcs[args.service](session,m,d)
    print(f"[seed] {args.service}_db: {created} new rows; existing deterministic IDs retained")
    if args.expect_existing and created != 0:
        raise RuntimeError(f"Idempotence check failed: {created} new rows on repeat seed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

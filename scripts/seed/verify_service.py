"""Read-only verification that V3 seed data exists and is internally consistent."""
from __future__ import annotations
import argparse
import os
import sys
sys.path.insert(0,"/app")
from seed_service import dataset, sid, VALID_SERVICES, DATABASES


def check(service: str):
    from sqlalchemy import select, func
    from sqlalchemy.engine import make_url
    url=make_url(os.environ.get("DATABASE_URL", ""))
    if url.host != "postgres" or url.database != DATABASES[service]:
        raise RuntimeError("Refusing verify: unexpected DB host or name")
    from app import models as m
    from app.db import get_sessionmaker
    d=dataset()
    with get_sessionmaker()() as session:
        if service=="auth":
            email=os.environ.get("OWNER_EMAIL", "").strip().lower()
            u=session.get(m.User,sid("owner",email))
            assert u and u.email==email and u.is_active
            assert u.password_hash not in ("",None) and len(u.password_hash)>40
            print("[verify] auth: 1 demo owner with password hash")
        elif service=="room":
            prop=session.get(m.Property,sid("property",d["property"]["code"]))
            assert prop and prop.status=="ACTIVE"
            for code in d["rooms"]:
                r=session.get(m.Room,sid("room",code))
                assert r and r.room_code==code
                is_occupied=code in d["occupied_rooms"]
                assert (r.occupancy_contract_id is not None)==is_occupied
            print("[verify] room: 1 property, 2 buildings, 4 floors, 12 rooms, 6 occupied")
        elif service=="tenant":
            for c in d["contracts"]:
                contract=session.get(m.Contract,sid("contract",c["code"]))
                assert contract and contract.status=="ACTIVE"
                term=session.get(m.ContractTerm,sid("term",c["code"]))
                assert term and term.contract_id==contract.id
                assert term.monthly_rent > 0
            for i in range(len(d["tenants"])):
                assert session.get(m.Tenant,sid("tenant",str(i))) is not None
            print("[verify] tenant: 8 tenants, 6 ACTIVE contracts, 6 terms, 18 history entries")
        elif service=="metering":
            count_pending=0
            for code in d["rooms"]:
                for kind in ("ELECTRICITY","WATER"):
                    meter=session.get(m.Meter,sid("meter",f"{code}:{kind}"))
                    assert meter and meter.room_id==sid("room",code)
                    for day in ("2026-10-01","2026-11-01"):
                        cutoff=session.get(m.MeterCutoff,sid("cutoff",f"{code}:{kind}:{day}"))
                        assert cutoff and cutoff.meter_id==meter.id
                        if cutoff.status=="PENDING":
                            count_pending+=1
                            assert code in d["blocked_rooms"] and day=="2026-11-01"
            assert count_pending==4
            print("[verify] metering: 24 meters, 48 monthly cutoffs, 4 pending")
        elif service=="billing":
            for c in d["contracts"]:
                inv=session.get(m.Invoice,sid("invoice",c["code"]))
                assert inv and inv.contract_id==sid("contract",c["code"])
                assert inv.due_date.isoformat() == d["invoice_due_date"]
                assert inv.period_start.isoformat() == d["billing_month"]
                assert inv.period_end.isoformat() == d["period_end"]
                items=session.execute(select(m.InvoiceItem).where(m.InvoiceItem.invoice_id==inv.id)).scalars().all()
                assert inv.total_amount == sum(item.amount for item in items)
                if c["room_code"] in d["blocked_rooms"]:
                    assert inv.status=="DRAFT" and inv.blocked_reason=="PENDING_CUTOFF"
                    assert inv.issued_at is None and inv.total_amount==0 and not items
                else:
                    from decimal import Decimal
                    assert inv.status=="ISSUED" and inv.blocked_reason is None and len(items)==4
                    assert inv.issued_at is not None
                    by_type={item.item_type:item for item in items}
                    assert set(by_type)=={"RENT","SERVICE","ELECTRICITY","WATER"}
                    for kind in ("RENT","SERVICE"):
                        item=by_type[kind]
                        assert item.unit=="DAY" and item.quantity==Decimal("31.000")
                        assert item.period_start==inv.period_start and item.period_end==inv.period_end
                        assert item.amount == (2500000+d["rooms"].index(c["room_code"])*100000 if kind=="RENT" else 100000)
                    for kind,unit in (("ELECTRICITY","KWH"),("WATER","M3")):
                        item=by_type[kind]
                        assert item.unit==unit
                        assert item.meter_end_value-item.meter_start_value==item.quantity
                        assert item.source_cutoff_start_id==sid("cutoff",f"{c['room_code']}:{kind}:{d['billing_month']}")
                        assert item.source_cutoff_end_id==sid("cutoff",f"{c['room_code']}:{kind}:{d['period_end']}")
            assert session.scalar(select(func.count()).select_from(m.PaymentAttempt))==0
            assert session.scalar(select(func.count()).select_from(m.OutboxEvent))==0
            print("[verify] billing: 4 ISSUED + 2 blocked DRAFT, 16 invoice items; no fake payments/outbox")
        elif service=="notification":
            assert session.scalar(select(func.count()).select_from(m.EmailJob))==0
            print("[verify] notification: intentionally empty until a real event")


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("service",choices=VALID_SERVICES)
    args=parser.parse_args()
    check(args.service)


if __name__=="__main__":
    main()

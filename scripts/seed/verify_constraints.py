"""Non-destructive PostgreSQL constraint checks, each invalid insert rolled back to SAVEPOINT."""
from __future__ import annotations
import argparse
import sys
import uuid
from datetime import date
from decimal import Decimal
sys.path.insert(0,"/app")
from seed_service import dataset,sid,midnight_vn,VALID_SERVICES


def assert_rejected(session, entity, expected_codes, message):
    from sqlalchemy.exc import IntegrityError
    savepoint=session.begin_nested()
    try:
        session.add(entity)
        try:
            session.flush()
        except IntegrityError as ex:
            code=getattr(ex.orig,"sqlstate",None)
            if code not in expected_codes:
                raise AssertionError(f"{message}: unexpected PostgreSQL error {code}") from ex
            print(f"[constraint] {message}: rejected ({code})")
        else:
            raise AssertionError(f"{message}: invalid row was ACCEPTED")
    finally:
        savepoint.rollback()


def run(service):
    from app import models as m
    from app.db import get_sessionmaker
    d=dataset()
    with get_sessionmaker()() as session:
        if service=='room':
            assert_rejected(session,m.Room(id=uuid.uuid4(),
                property_id=sid('property',d['property']['code']),
                floor_id=sid('floor','A1'),room_code='A101',area_m2=Decimal('20.00'),
                listed_rent=1000000,status='ACTIVE'), {'23505'},'duplicate room code')
        elif service=='tenant':
            assert_rejected(session,m.Contract(id=uuid.uuid4(),contract_code='DEMO-CONFLICT-TEMP',
                room_id=sid('room','A101'),room_code_snapshot='A101',
                representative_tenant_id=sid('tenant','0'),start_date=date(2026,10,1),
                end_date=date(2026,12,31),status='ACTIVE'), {'23P01'},'overlapping active contract')
        elif service=='metering':
            assert_rejected(session,m.MeterReading(meter_id=sid('meter','A101:ELECTRICITY'),
                measured_at=midnight_vn('2026-10-01'),reading_value=Decimal('9999.000'),
                validation_status='VALID'), {'23505'},'duplicate meter reading')
        elif service=='billing':
            c=d['contracts'][0]
            assert_rejected(session,m.Invoice(id=uuid.uuid4(),invoice_code='DEMO-DUPLICATE-TEMP',
                contract_id=sid('contract',c['code']),room_id=sid('room','A101'),
                invoice_type='PERIODIC',billing_month=date(2026,10,1),
                period_start=date(2026,10,1),period_end=date(2026,11,1),
                status='ISSUED',total_amount=0,due_date=date(2026,11,15),
                tenant_name_snapshot='Demo',room_code_snapshot='A101'), {'23505','23P01'},'duplicate periodic invoice')
        else:
            return
    print(f'[constraint] {service}: checks passed, data unchanged')


if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('service',choices=VALID_SERVICES)
    run(ap.parse_args().service)

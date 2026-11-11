"""Read-only (rollback-only) regression for room_v3_003 hierarchy invariants.

The 003 guard rejects any parent-key change, even if there are no rooms.
This eliminates the inter-transaction write skew in the previous conditional
room-existence triggers. Test uses savepoints and rolls back everything.
"""
from __future__ import annotations
import sys
import uuid
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

sys.path.insert(0, '/app')


def assert_rejected(session, sql: str, params: dict, label: str) -> None:
    nested = session.begin_nested()
    try:
        try:
            session.execute(text(sql), params)
        except DBAPIError as exc:
            code = getattr(exc.orig, 'sqlstate', None)
            if code != '23514':
                raise AssertionError(f'{label}: unexpected SQLSTATE={code}') from exc
            print(f'[room003] {label}: rejected (23514)')
        else:
            raise AssertionError(f'{label}: invalid reparent was ACCEPTED')
    finally:
        nested.rollback()


def main() -> None:
    from app.db import get_sessionmaker
    from app import models as m
    with get_sessionmaker()() as session:
        try:
            existing = session.query(m.Building).order_by(m.Building.name).all()
            if len(existing) < 2:
                raise RuntimeError('Requires demo seed with at least two buildings')
            b0, b1 = existing[:2]

            # Uncommitted auxiliary property/building/floor; entire session
            # is rolled back, so no test fixtures remain in the database.
            other_property = m.Property(id=uuid.uuid4(), name='TEMP_P00', address='TEMP')
            session.add(other_property)
            session.flush()
            empty_building = m.Building(id=uuid.uuid4(), property_id=b0.property_id, name='TEMP_EMPTY_P00')
            session.add(empty_building)
            session.flush()
            empty_floor = m.Floor(id=uuid.uuid4(), building_id=b0.id, floor_number=99999, name='TEMP_EMPTY_P00')
            session.add(empty_floor)
            session.flush()

            # Both reparent attempts MUST fail even without existing rooms.
            assert_rejected(session,
                'UPDATE buildings SET property_id=:pid WHERE id=:bid',
                {'pid': other_property.id, 'bid': empty_building.id},
                'move empty building to another property')
            assert_rejected(session,
                'UPDATE floors SET building_id=:bid WHERE id=:fid',
                {'bid': b1.id, 'fid': empty_floor.id},
                'move empty floor to another building')

            # Updating unrelated fields remains permitted; no parent move.
            session.execute(text('UPDATE buildings SET name=name WHERE id=:bid'), {'bid': b0.id})
            session.execute(text('UPDATE floors SET name=name WHERE id=:fid'), {'fid': empty_floor.id})
            print('[room003] unrelated-field updates allowed')
        finally:
            session.rollback()
    print('[room003] PASS (all changes rolled back)')


if __name__ == '__main__':
    main()

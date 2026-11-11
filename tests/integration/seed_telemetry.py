"""Create only 2 temporary meters in the disposable P06 test project."""
import os
from uuid import uuid4
from app import repository as repo
from app.db import get_sessionmaker
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from app import models as m

if os.getenv('P06_EPHEMERAL_TEST') != '1' or not os.getenv('P06_PROJECT_NAME','').startswith(('p06test','p06ci')):
    raise RuntimeError('Refusing to seed outside a disposable P06 project')
with get_sessionmaker()() as session:
    with session.begin():
        room=uuid4()
        repo.ensure_meter(session,room,'ELECTRICITY')
        repo.ensure_meter(session,room,'WATER')
        
        electricity = next(
            meter
            for meter in repo.meters_for_room(session, room)
            if meter.meter_type == "ELECTRICITY"
        )

        session.add(
            m.MeterReading(
                meter_id=electricity.id,
                measured_at=(
                    datetime.now(timezone.utc).replace(microsecond=0)
                    - timedelta(days=1)
                ),
                reading_value=Decimal("1000000.000"),
                validation_status="VALID",
            )
        )

    print('Created 2 active demo meters in disposable PostgreSQL')

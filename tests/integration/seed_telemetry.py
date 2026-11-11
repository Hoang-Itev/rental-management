"""Create only 2 temporary meters in the disposable P06 test project."""
import os
from uuid import uuid4
from app import repository as repo
from app.db import get_sessionmaker
if os.getenv('P06_EPHEMERAL_TEST') != '1' or not os.getenv('P06_PROJECT_NAME','').startswith(('p06test','p06ci')):
    raise RuntimeError('Refusing to seed outside a disposable P06 project')
with get_sessionmaker()() as session:
    with session.begin():
        room=uuid4()
        repo.ensure_meter(session,room,'ELECTRICITY')
        repo.ensure_meter(session,room,'WATER')
    print('Created 2 active demo meters in disposable PostgreSQL')

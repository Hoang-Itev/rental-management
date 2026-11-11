"""P05 one physical cutoff, two logical handover reasons."""
from datetime import datetime,timezone
from uuid import uuid4
from sqlalchemy import select,func
from app.service import MeteringService
from app import models as m
from app.lifecycle import FutureEvent
import pytest


def message(kind,contract,room,when):
    return {'event_id':str(uuid4()),'event_type':kind,'event_version':1,
            'aggregate_id':str(contract),'occurred_at':when,'effective_at':when,
            'correlation_id':str(uuid4()),'data':{'contract_id':str(contract),'room_id':str(room)}}


@pytest.mark.parametrize('reverse',[False,True])
def test_end_start_same_boundary_physical_cutoff_shared(make_session,reverse):
    room,a,b=uuid4(),uuid4(),uuid4()
    same='2026-11-16T00:00:00+07:00'
    start=message('ContractStarted',b,room,same)
    end=message('ContractEnded',a,room,same)
    with make_session() as db:
        svc=MeteringService(db)
        for ev in ([start,end] if reverse else [end,start]):
            assert svc.process_contract_event(ev,now=datetime(2026,11,20,tzinfo=timezone.utc))
        assert db.scalar(select(func.count()).select_from(m.Meter))==2
        cutoffs=list(db.scalars(select(m.MeterCutoff)))
        assert len(cutoffs)==2
        assert all(c.cutoff_type=='CONTRACT_START' and c.contract_id==b for c in cutoffs)
        reasons=list(db.scalars(select(m.MeterCutoffReason)))
        assert len(reasons)==4
        assert {r.reason_type for r in reasons}=={'CONTRACT_START','CONTRACT_END'}
        assert svc.process_contract_event(start,now=datetime(2026,11,20,tzinfo=timezone.utc)) is False


def test_future_handover_deferred(make_session):
    room=uuid4();a=uuid4()
    with make_session() as db:
        with pytest.raises(FutureEvent):
            MeteringService(db).process_contract_event(message('ContractStarted',a,room,'2027-11-01T00:00:00+07:00'),
                now=datetime(2026,11,11,tzinfo=timezone.utc))
        assert db.scalar(select(func.count()).select_from(m.Meter))==0

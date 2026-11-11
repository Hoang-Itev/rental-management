from uuid import uuid4

from sqlalchemy import select

from app import models as m, repository as repo, schemas as s
from app.service import RoomService


def test_repository_lookup_pagination_and_dedupe(test_service):
    svc=test_service
    p=svc.create_property(s.PropertyCreate(name='P',address='A'))
    assert repo.get(svc.session,m.Property,p.id)==p
    assert repo.get(svc.session,m.Property,uuid4()) is None
    assert repo.get(svc.session,m.Property,p.id,lock=True)==p
    assert repo.page(svc.session,m.Property,page_number=1,page_size=1)[1]==1
    assert repo.any_active(svc.session,m.Building,m.Building.property_id,p.id) is False
    assert repo.code_exists(svc.session,p.id,['A1']) is False
    assert repo.outbox_by_dedupe(svc.session,'unknown') is None

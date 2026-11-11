from decimal import Decimal
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app import schemas as s


def test_room_codes_are_normalized():
    obj=s.RoomCreateItem(room_code='a-1',area_m2=Decimal('1.25'),listed_rent=0)
    assert obj.room_code=='A-1'
    assert s.RoomPatch(room_code='z_9').room_code=='Z_9'


@pytest.mark.parametrize('code',['','spaces here','x!' ,'@',' '])
def test_invalid_room_codes(code):
    with pytest.raises(ValidationError):
        s.RoomCreateItem(room_code=code,area_m2='20.00',listed_rent=1)


@pytest.mark.parametrize('value',['0','-3.0','1.001','9999999.99','NaN'])
def test_invalid_area(value):
    with pytest.raises(ValidationError):
        s.RoomCreateItem(room_code='A1',area_m2=value,listed_rent=1)


@pytest.mark.parametrize('value',[-1,1.2,'abcd'])
def test_invalid_rent(value):
    with pytest.raises(ValidationError):
        s.RoomCreateItem(room_code='A1',area_m2='2.00',listed_rent=value)


def test_room_bulk_guard_and_patch_shape():
    obj=s.RoomCreateItem(room_code='A1',area_m2='10.00',listed_rent=500)
    with pytest.raises(ValidationError):s.RoomBulkCreate(rooms=[])
    with pytest.raises(ValidationError):s.RoomBulkCreate(rooms=[obj,obj])
    with pytest.raises(ValidationError):s.RoomBulkCreate(rooms=[obj]*101)
    with pytest.raises(ValidationError):s.RoomPatch()
    with pytest.raises(ValidationError):s.RoomPatch(status=None)
    with pytest.raises(ValidationError):s.RoomPatch(floor_id=uuid4())
    with pytest.raises(ValidationError):s.PropertyPatch(name=None)
    with pytest.raises(ValidationError):s.BuildingPatch(status=None)
    with pytest.raises(ValidationError):s.FloorPatch(status=None)

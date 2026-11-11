from __future__ import annotations
from uuid import uuid4
import httpx
import pytest
from app.clients import RoomClient,RoomUnavailable
from app.config import TenantSettings


def settings():return TenantSettings(SERVICE_TOKEN='z'*32,ROOM_URL='http://room:8000')


def test_room_client_uses_private_rest_and_service_token():
    rid=uuid4()
    def responder(request):
        assert request.url.path==f'/internal/v1/rooms/{rid}/validation'
        assert request.headers['x-service-token']=='z'*32
        assert request.headers.get('authorization') is None
        return httpx.Response(200,json={'room_id':str(rid),'exists':True,'operational':True,'room_code':'R1'})
    client=RoomClient(settings(),httpx.MockTransport(responder))
    r=client.validate(rid)
    assert r.exists and r.operational and r.room_code=='R1'


@pytest.mark.parametrize('response',[
    httpx.Response(403,json={'detail':'forbidden'}),
    httpx.Response(503,json={'detail':'service down'}),
    httpx.Response(200,json={'unknown':1}),
    httpx.Response(200,text='not-json'),
])
def test_room_client_fails_closed(response):
    client=RoomClient(settings(),httpx.MockTransport(lambda req:response))
    with pytest.raises(RoomUnavailable):client.validate(uuid4())


def test_room_client_rejects_mismatched_room():
    actual=uuid4()
    client=RoomClient(settings(),httpx.MockTransport(lambda req:httpx.Response(200,json={
        'room_id':str(actual),'exists':True,'operational':True,'room_code':'X'})))
    with pytest.raises(RoomUnavailable):client.validate(uuid4())


def test_room_client_network_timeout():
    def failed(request):raise httpx.ConnectTimeout('timeout')
    client=RoomClient(settings(),httpx.MockTransport(failed))
    with pytest.raises(RoomUnavailable):client.validate(uuid4())

from __future__ import annotations

from uuid import uuid4

from app.service import MeteringService
from tests.support import example


def test_service_token_required(client):
    room = uuid4()
    url = f"/internal/v1/rooms/{room}/meters"
    assert client.get(url).status_code == 403
    assert client.get(url, headers={"X-Service-Token": "bad"}).status_code == 403
    assert client.get(url, headers={"X-Service-Token": "s" * 32}).status_code == 200
    assert client.get("/internal/v1/meters").status_code == 403


def test_read_only_meter_apis(client, make_session):
    e = example()
    with make_session() as db:
        MeteringService(db).process_room_created(e)
    headers = {"X-Service-Token": "s" * 32}
    res = client.get("/internal/v1/rooms/" + e["data"]["room_id"] + "/meters", headers=headers)
    assert res.status_code == 200, res.text
    assert sorted(x["meter_type"] for x in res.json()["items"]) == ["ELECTRICITY", "WATER"]
    res = client.get("/internal/v1/meters", headers=headers)
    assert res.status_code == 200 and len(res.json()["items"]) == 2
    assert client.get("/internal/v1/meters?status=BAD", headers=headers).status_code == 422


def test_health(client):
    assert client.get("/health").status_code == 200

def test_p06_owner_reading_and_alert_api(client,make_session):
    from uuid import uuid4
    from app import repository as repo
    from app.service import MeteringService
    from tests.test_service import sample
    with make_session() as db:
        rid=uuid4()
        repo.ensure_meter(db,rid,'WATER')
        meter=repo.meters_for_room(db,rid)[0]
        MeteringService(db).record_telemetry(sample(meter.id))
        MeteringService(db).record_telemetry({**sample(meter.id),'reading_value':'500'})
        meter_id=str(meter.id)
        db.commit()
    resp=client.get(f'/api/v1/meters/{meter_id}/readings')
    assert resp.status_code==200,resp.text
    assert resp.json()['meta']['total']==1
    assert resp.json()['items'][0]['validation_status']=='VALID'
    alerts=client.get(f'/api/v1/meters/{meter_id}/alerts')
    assert alerts.status_code==200,alerts.text
    assert alerts.json()['meta']['total']==1
    assert client.get('/api/v1/meters/'+str(uuid4())+'/readings').status_code==404


def test_p06_global_alert_listing_matches_openapi(client,make_session):
    res=client.get('/api/v1/meter-alerts?status=OPEN&alert_type=CONFLICTING_DUPLICATE')
    assert res.status_code==200,res.text
    assert isinstance(res.json()['items'],list)
    assert client.get('/api/v1/meter-alerts?status=INVALID').status_code==422
    assert client.get('/api/v1/meter-alerts?page=0').status_code==422

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


def test_p07_owner_cutoff_manual_confirm_revision_and_internal_projection(client, make_session):
    from datetime import datetime, timezone
    from decimal import Decimal
    from app import models as m, repository as repo
    actor = uuid4()
    room = uuid4()
    with make_session() as db:
        repo.ensure_meter(db, room, 'ELECTRICITY')
        meter = repo.meters_for_room(db, room)[0]
        cutoff = m.MeterCutoff(
            id=uuid4(), meter_id=meter.id, cutoff_type='MONTHLY',
            cutoff_at=datetime(2026, 11, 1, tzinfo=timezone.utc),
            source='AUTOMATIC', status='PENDING')
        db.add(cutoff)
        db.commit()
        cutoff_id = str(cutoff.id)
        mid = str(meter.id)
    listing = client.get(f'/api/v1/meter-cutoffs?meter_id={mid}&status=PENDING')
    assert listing.status_code == 200 and listing.json()['meta']['total'] == 1
    assert listing.json()['items'][0]['reading_value'] is None
    assert client.get('/api/v1/meter-cutoffs/'+cutoff_id).status_code == 200
    payload = {'reading_value':'100.000', 'manual_reason':'Owner checked mechanical counter'}
    # Do not authorize mutations without Nginx's verified identity header.
    assert client.post(f'/api/v1/meter-cutoffs/{cutoff_id}/confirm', json=payload).status_code == 422
    headers = {'X-Auth-User-Id':str(actor)}
    confirmed = client.post(f'/api/v1/meter-cutoffs/{cutoff_id}/confirm',
                            headers=headers, json=payload)
    assert confirmed.status_code == 200, confirmed.text
    assert confirmed.json()['status']=='CONFIRMED'
    assert confirmed.json()['confirmed_by']==str(actor)
    assert client.post(f'/api/v1/meter-cutoffs/{cutoff_id}/confirm',
                       headers=headers, json=payload).status_code == 409
    changed = client.post(f'/api/v1/meter-cutoffs/{cutoff_id}/corrections', headers=headers,
                          json={**payload, 'reading_value':'101.000'})
    assert changed.status_code == 201, changed.text
    new_id = changed.json()['id']
    assert changed.json()['supersedes_id'] == cutoff_id
    assert client.get(f'/api/v1/meter-cutoffs/{cutoff_id}').json()['status']=='SUPERSEDED'
    internal = client.get(f'/internal/v1/rooms/{room}/cutoffs',
                          headers={'X-Service-Token':'s'*32})
    assert internal.status_code == 200, internal.text
    assert internal.json()['meta']['total'] == 1
    assert internal.json()['items'][0]['id'] == new_id
    assert client.get(f'/internal/v1/rooms/{room}/cutoffs').status_code == 403
    assert client.get(f'/api/v1/meter-cutoffs?status=garbage').status_code == 422
    assert client.get(f'/api/v1/meter-cutoffs?from=2026-12-01T00:00:00Z&to=2026-11-01T00:00:00Z').status_code == 422


def test_p07_internal_and_owner_cutoff_job(client,make_session):
    from app import repository as repo
    with make_session() as db:
        repo.ensure_meter(db,uuid4(),'WATER')
        db.commit()
    resp=client.post('/api/v1/jobs/meters/cutoffs')
    assert resp.status_code==200,resp.text
    assert set(resp.json())=={'monthly_created','auto_confirmed','offline_alerts_created'}
    assert client.get('/openapi.json').status_code == 200
    spec=client.get('/openapi.json').json()
    assert '/api/v1/meter-cutoffs/{cutoff_id}/corrections' in spec['paths']
    assert '/internal/v1/rooms/{room_id}/cutoffs' in spec['paths']


def test_p07_monthly_job_validates_vn_boundary(client):
    # 2026-11-01 00:00 local = 2026-10-31 17:00 UTC.
    ok = client.post('/api/v1/jobs/meters/monthly-cutoffs/run',
                     json={'cutoff_at':'2026-10-31T17:00:00Z'})
    assert ok.status_code==202, ok.text
    assert ok.json()['cutoff_at'].startswith('2026-10-31T17:00:00')
    wrong = client.post('/api/v1/jobs/meters/monthly-cutoffs/run',
                        json={'cutoff_at':'2026-11-01T00:00:00Z'})
    assert wrong.status_code==422


def test_owner_room_meter_listing(client, make_session):
    event = example()
    with make_session() as db:
        MeteringService(db).process_room_created(event)
    result = client.get('/api/v1/rooms/' + event['data']['room_id'] + '/meters')
    assert result.status_code == 200
    assert sorted(m['meter_type'] for m in result.json()['items']) == ['ELECTRICITY', 'WATER']
    assert client.get(f'/api/v1/rooms/{uuid4()}/meters').json() == {'items': []}
    assert client.get('/api/v1/rooms/invalid/meters').status_code == 422

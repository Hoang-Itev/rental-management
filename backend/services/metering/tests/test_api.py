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

"""Manual local Phase I checkpoint: Login -> Create tree+room -> observe meters.

Writes ONE real test tree to local database. It does NOT delete it afterward.
Run only from scripts/test_p03_gateway.ps1 after starting P03 overlay workers.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from urllib.request import Request, urlopen
from urllib.error import HTTPError
from uuid import uuid4

BASE = os.getenv("TEST_AUTH_BASE_URL", "http://127.0.0.1:8080")


def post(path, data, token=None):
    headers = {"Content-Type": "application/json", "Accept": "application/json"}
    if token:
        headers["Authorization"] = "Bearer " + token
    req = Request(BASE + path, headers=headers, data=json.dumps(data).encode(), method="POST")
    try:
        with urlopen(req, timeout=15) as res:
            if res.status not in (200, 201):
                raise AssertionError(f"{path}: HTTP {res.status}")
            return res.json() if hasattr(res, "json") else json.load(res)
    except HTTPError as exc:
        raise AssertionError(f"{path}: HTTP {exc.code} ({exc.read()[:240]!r})") from exc


def meters_from_container(room_id):
    # The service token stays INSIDE the container, never exported to PowerShell.
    script = (
        "import os,json,urllib.request;"
        "url='http://127.0.0.1:8000/internal/v1/rooms/" + room_id + "/meters';"
        "req=urllib.request.Request(url, headers={'X-Service-Token':os.environ['SERVICE_TOKEN']});"
        "print(urllib.request.urlopen(req,timeout=5).read().decode())"
    )
    cmd = ["docker", "compose", "-f", "compose.yaml", "-f", "compose.runtime.yaml",
           "exec", "-T", "metering", "python", "-c", script]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=20)
    if result.returncode != 0:
        raise RuntimeError("Metering internal read failed: " + result.stderr[-250:])
    return json.loads(result.stdout)["items"]


def main():
    email = os.environ["TEST_AUTH_EMAIL"]
    password = os.environ["TEST_AUTH_PASSWORD"]
    jwt = post("/api/v1/auth/login", {"email": email, "password": password})["access_token"]
    print("[PASS] owner login through Nginx")
    suffix = uuid4().hex[:10]
    prop = post("/api/v1/properties", {"name": "P03 Demo " + suffix,
                                          "address": "P03 integration demo"}, jwt)
    building = post(f"/api/v1/properties/{prop['id']}/buildings", {"name": "A"}, jwt)
    floor = post(f"/api/v1/buildings/{building['id']}/floors", {"floor_number": 1}, jwt)
    room = post(f"/api/v1/floors/{floor['id']}/rooms", {"room_code": "R101",
                                                               "area_m2": "22.50", "listed_rent": 2500000}, jwt)
    print("[PASS] owner creates property, building, floor, room through Nginx")
    deadline = time.monotonic() + 60
    while time.monotonic() < deadline:
        meters = meters_from_container(room["id"])
        if len(meters) == 2:
            assert {m["meter_type"] for m in meters} == {"ELECTRICITY", "WATER"}
            print("[PASS] RabbitMQ consumer created exactly ELECTRICITY and WATER")
            print("ROOM_ID=" + room["id"])
            print("METER_IDS=" + ",".join(m["id"] for m in meters))
            print("P03 GATEWAY CHECKPOINT OK (created one persistent demo tree)")
            return 0
        time.sleep(1)
    raise AssertionError("No two meters within 60 seconds; inspect workers with docker compose logs")


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (AssertionError, OSError, RuntimeError, KeyError, ValueError) as exc:
        print("P03 GATEWAY CHECK FAILED: " + str(exc), file=sys.stderr)
        raise SystemExit(1)

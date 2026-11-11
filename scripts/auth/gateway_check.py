"""Real Nginx + Auth + PostgreSQL smoke, no third-party Python packages.

Requires an Auth owner already seeded in the target environment. Does not mutate DB
except last_login_at from a successful login. Never prints passwords or tokens.
"""
from __future__ import annotations

import json
import os
import sys
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

BASE = os.getenv("TEST_AUTH_BASE_URL", "http://127.0.0.1:8080").rstrip("/")
EMAIL = os.getenv("TEST_AUTH_EMAIL", "")
PASSWORD = os.getenv("TEST_AUTH_PASSWORD", "")


def call(path: str, *, method: str = "GET", payload: dict | None = None, token: str | None = None):
    headers = {"Accept": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    body = None
    if payload is not None:
        headers["Content-Type"] = "application/json"
        body = json.dumps(payload).encode("utf-8")
    request = Request(BASE + path, data=body, method=method, headers=headers)
    try:
        with urlopen(request, timeout=15) as response:
            return response.status, response.read()
    except HTTPError as exc:
        return exc.code, exc.read()


def status(expected: int, actual: int, label: str):
    if actual != expected:
        raise AssertionError(f"{label}: expected HTTP {expected}, got HTTP {actual}")
    print(f"[PASS] {label}: HTTP {actual}")


def main() -> int:
    if not EMAIL or not PASSWORD:
        print("Missing TEST_AUTH_EMAIL / TEST_AUTH_PASSWORD", file=sys.stderr)
        return 2
    try:
        status(200, call("/gateway-health")[0], "gateway health")
        status(401, call("/api/v1/auth/me")[0], "profile without token")
        status(401, call("/api/v1/auth/me", token="invalid.token.here")[0], "profile with fake token")
        status(404, call("/internal/v1/auth/verify")[0], "internal verify not public")
        bad_code, bad_body = call("/api/v1/auth/login", method="POST", payload={"email": EMAIL, "password": PASSWORD + "incorrect"})
        status(401, bad_code, "wrong password")
        bad = json.loads(bad_body)
        if bad.get("code") != "UNAUTHORIZED":
            raise AssertionError("wrong password error format")
        code, body = call("/api/v1/auth/login", method="POST", payload={"email": EMAIL, "password": PASSWORD})
        status(200, code, "correct password")
        data = json.loads(body)
        token = data["access_token"]
        if data.get("token_type") != "bearer" or data.get("expires_in", 0) <= 0:
            raise AssertionError("invalid token response")
        if data["user"]["email"].lower() != EMAIL.lower() or "password_hash" in data["user"]:
            raise AssertionError("incorrect or unsafe user DTO")
        code, body = call("/api/v1/auth/me", token=token)
        status(200, code, "valid JWT passes Nginx auth_request")
        me = json.loads(body)
        if me["id"] != data["user"]["id"]:
            raise AssertionError("identity mismatch between login and me")
        status(401, call("/api/v1/auth/me", token=token + "tampered")[0], "tampered JWT rejected")
        print("AUTH GATEWAY E2E OK (8 checks, real DB and Nginx)")
        return 0
    except (AssertionError, URLError, json.JSONDecodeError, KeyError) as exc:
        print(f"AUTH GATEWAY E2E FAILED: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

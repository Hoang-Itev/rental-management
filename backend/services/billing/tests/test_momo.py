from datetime import datetime, timezone
from types import SimpleNamespace

import httpx
import pytest

from app.config import Settings
from app.momo import MomoClient, MomoUnavailable


def test_bad_provider_checkout_url_is_ambiguous():
    settings = Settings(
        service_token="unit-test-only-service-token-value", momo_partner_code="TEST",
        momo_access_key="unit-access", momo_secret_key="unit-secret",
        momo_ipn_url="https://demo.example.com/webhooks/momo/ipn",
    )

    def reply(_):
        return httpx.Response(200, json={
            "partnerCode": "TEST", "orderId": "order", "requestId": "request", "amount": 1500000,
            "resultCode": 0, "payUrl": "https://demo.example.com/unsafe-destination",
        })

    attempt = SimpleNamespace(order_id="order", request_id="request", amount=1500000,
                              created_at=datetime.now(timezone.utc))
    with httpx.Client(transport=httpx.MockTransport(reply)) as http:
        with pytest.raises(MomoUnavailable):
            MomoClient(http, settings).create(attempt)


@pytest.fixture
def configured_settings():
    return Settings(
        service_token="unit-test-only-service-token-value", momo_partner_code="TEST",
        momo_access_key="unit-access", momo_secret_key="unit-secret",
        momo_ipn_url="https://gateway.example.com/webhooks/momo/ipn",
    )


def test_momo_configuration_is_read_from_environment(monkeypatch):
    values = {
        "SERVICE_TOKEN": "unit-test-only-service-token-value",
        "MOMO_PARTNER_CODE": "ENV_PARTNER", "MOMO_ACCESS_KEY": "env-access",
        "MOMO_SECRET_KEY": "env-secret",
        "MOMO_IPN_URL": "https://tunnel.example.com/webhooks/momo/ipn",
    }
    for key, value in values.items():
        monkeypatch.setenv(key, value)
    client = MomoClient(None, Settings())
    assert client.enabled
    assert client.partner_code == values["MOMO_PARTNER_CODE"]
    assert client.access_key == values["MOMO_ACCESS_KEY"]
    assert client.secret_key == values["MOMO_SECRET_KEY"]
    assert str(client.settings.momo_ipn_url) == values["MOMO_IPN_URL"]


@pytest.mark.parametrize("missing", ["MOMO_PARTNER_CODE", "MOMO_ACCESS_KEY", "MOMO_SECRET_KEY", "MOMO_IPN_URL"])
def test_missing_configuration_disables_real_checkout(monkeypatch, missing):
    for key, value in {
        "MOMO_PARTNER_CODE": "TEST", "MOMO_ACCESS_KEY": "access",
        "MOMO_SECRET_KEY": "secret", "MOMO_IPN_URL": "https://example.com/webhooks/momo/ipn",
    }.items():
        monkeypatch.setenv(key, "" if key == missing else value)
    assert not MomoClient(None, Settings(service_token="unit-test-only-service-token-value")).enabled


@pytest.mark.parametrize("operation", ["create", "query"])
@pytest.mark.parametrize("failure", ["html_504", "timeout", "invalid_json", "mismatched_order"])
def test_provider_failures_are_logged_without_secrets(configured_settings, caplog, operation, failure):
    def reply(request):
        if failure == "timeout":
            raise httpx.ReadTimeout("Do not log this raw error: unit-secret", request=request)
        if failure == "html_504":
            return httpx.Response(504, text="<html>openresty APISIX unit-secret</html>")
        if failure == "invalid_json":
            return httpx.Response(200, text="not JSON unit-secret")
        return httpx.Response(200, json={
            "partnerCode": "TEST", "orderId": "different-order", "requestId": "request",
            "resultCode": 0, "payUrl": "https://test-payment.momo.vn/pay?token=private",
        })

    attempt = SimpleNamespace(order_id="order", request_id="request", amount=1500000)
    with httpx.Client(transport=httpx.MockTransport(reply)) as http:
        with pytest.raises(MomoUnavailable):
            getattr(MomoClient(http, configured_settings), operation)(attempt)
    assert f"operation={operation}" in caplog.text
    assert "order_id=order" in caplog.text
    if failure == "html_504":
        assert "http_status=504" in caplog.text
    for private in ("unit-secret", "unit-access", "token=private", "APISIX"):
        assert private not in caplog.text


def test_real_create_payload_uses_configured_callback_and_signature(configured_settings):
    import hashlib
    import hmac
    import json

    def reply(request):
        data = json.loads(request.content)
        assert str(request.url) == "https://test-payment.momo.vn/v2/gateway/api/create"
        assert data["ipnUrl"] == str(configured_settings.momo_ipn_url)
        assert data["redirectUrl"] == "http://localhost:8080/public/v1/payments/momo/return"
        assert data["requestType"] == "payWithATM"
        raw = (
            "accessKey=unit-access&amount=1500000&extraData="
            "&ipnUrl=https://gateway.example.com/webhooks/momo/ipn"
            "&orderId=order&orderInfo=Invoice payment order&partnerCode=TEST"
            "&redirectUrl=http://localhost:8080/public/v1/payments/momo/return"
            "&requestId=request&requestType=payWithATM"
        )
        assert data["signature"] == hmac.new(b"unit-secret", raw.encode(), hashlib.sha256).hexdigest()
        return httpx.Response(200, json={
            "partnerCode": "TEST", "orderId": "order", "requestId": "request", "amount": 1500000,
            "resultCode": 0, "payUrl": "https://test-payment.momo.vn/gateway/pay?t=test",
        })
    with httpx.Client(transport=httpx.MockTransport(reply)) as http:
        result = MomoClient(http, configured_settings).create(
            SimpleNamespace(order_id="order", request_id="request", amount=1500000))
    assert result.resultCode == 0

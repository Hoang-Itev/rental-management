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

"""MoMo Sandbox domestic ATM checkout, IPN and transaction query."""
import hashlib
import hmac
from uuid import uuid4
from urllib.parse import urlsplit

import httpx

from app.schemas import MomoResult

SANDBOX = "https://test-payment.momo.vn"
CREATE_FIELDS = ("amount", "extraData", "ipnUrl", "orderId", "orderInfo", "partnerCode",
                 "redirectUrl", "requestId", "requestType")
IPN_FIELDS = ("amount", "extraData", "message", "orderId", "orderInfo", "orderType",
              "partnerCode", "payType", "requestId", "responseTime", "resultCode", "transId")
QUERY_FIELDS = ("orderId", "partnerCode", "requestId")
FINAL_FAILURES = {1001, 1002, 1003, 1004, 1005, 1006, 1007, 1017, 1026}


class MomoUnavailable(Exception):
    pass


def signature(payload, fields, access_key, secret_key):
    canonical = "&".join([f"accessKey={access_key}", *(f"{name}={payload[name]}" for name in fields)])
    return hmac.new(secret_key.encode(), canonical.encode(), hashlib.sha256).hexdigest()


class MomoClient:
    def __init__(self, http, settings):
        self.http = http
        self.settings = settings
        self.partner_code = settings.momo_partner_code
        self.access_key = settings.momo_access_key.get_secret_value()
        self.secret_key = settings.momo_secret_key.get_secret_value()

    @property
    def enabled(self):
        return bool(self.partner_code and self.access_key and self.secret_key and self.settings.momo_ipn_url)

    def verify_ipn(self, ipn):
        expected = signature(ipn.model_dump(), IPN_FIELDS, self.access_key, self.secret_key)
        return ipn.partnerCode == self.partner_code and hmac.compare_digest(expected, ipn.signature.lower())

    def _post(self, operation, payload, fields):
        payload["signature"] = signature(payload, fields, self.access_key, self.secret_key)
        try:
            response = self.http.post(f"{SANDBOX}/v2/gateway/api/{operation}", json=payload)
            response.raise_for_status()
            result = MomoResult.model_validate(response.json())
            if (result.partnerCode, result.orderId, result.requestId) != (
                payload["partnerCode"], payload["orderId"], payload["requestId"],
            ):
                raise ValueError("Unmatched MoMo response")
            return result
        except (httpx.HTTPError, ValueError) as exc:
            raise MomoUnavailable("MoMo response unavailable or ambiguous") from exc

    def create(self, attempt):
        origin = str(self.settings.public_base_url).rstrip("/")
        result = self._post("create", {
            "partnerCode": self.partner_code, "partnerName": "Rental Management",
            "storeId": self.partner_code, "requestId": attempt.request_id, "orderId": attempt.order_id,
            "amount": attempt.amount, "orderInfo": f"Invoice payment {attempt.order_id}",
            "ipnUrl": str(self.settings.momo_ipn_url), "redirectUrl": f"{origin}/public/v1/payments/momo/return",
            "extraData": "", "requestType": "payWithATM", "lang": "vi",
        }, CREATE_FIELDS)
        if result.resultCode == 0:
            pay_url = urlsplit(result.payUrl or "")
            if (result.amount not in (None, attempt.amount) or pay_url.scheme != "https"
                    or pay_url.hostname != urlsplit(SANDBOX).hostname or pay_url.username or pay_url.password):
                raise MomoUnavailable("MoMo checkout response is incomplete")
        return result

    def query(self, attempt):
        return self._post("query", {
            "partnerCode": self.partner_code, "requestId": uuid4().hex,
            "orderId": attempt.order_id, "lang": "vi",
        }, QUERY_FIELDS)

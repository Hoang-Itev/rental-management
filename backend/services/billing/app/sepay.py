"""SePay Payment Gateway signed POST checkout (not an API JSON checkout call).

Docs: https://developer.sepay.vn/vi/cong-thanh-toan/API/don-hang/form-thanh-toan
The order_invoice_number identifies a single PaymentAttempt, not the rent invoice.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
from collections import OrderedDict

SIGNED_FIELDS = (
    "order_amount", "merchant", "currency", "operation", "order_description",
    "order_invoice_number", "customer_id", "payment_method",
    "success_url", "error_url", "cancel_url",
)
CHECKOUT_HOSTS = {
    "sandbox": "https://pay-sandbox.sepay.vn/v1/checkout/init",
    "production": "https://pay.sepay.vn/v1/checkout/init",
}


def sign_fields(fields: dict[str, str], secret: str) -> str:
    """Base64 HMAC-SHA256 of SePay's documented ordered comma-separated fields."""
    canonical = ",".join(f"{name}={fields[name]}" for name in SIGNED_FIELDS if name in fields)
    digest = hmac.new(secret.encode("utf-8"), canonical.encode("utf-8"), hashlib.sha256).digest()
    return base64.b64encode(digest).decode("ascii")


class SePayGateway:
    def __init__(self, settings):
        self.settings = settings

    @property
    def enabled(self) -> bool:
        merchant = self.settings.sepay_merchant_id
        key = self.settings.sepay_secret_key.get_secret_value()
        ipn_key = self.settings.sepay_ipn_secret_key.get_secret_value()
        if not (merchant and key and ipn_key):
            return False
        if self.settings.sepay_environment == "production" and (
            merchant.startswith("SP-TEST-") or key.startswith("spsk_test_")
        ):
            return False
        return True

    @property
    def action_url(self) -> str:
        return CHECKOUT_HOSTS[self.settings.sepay_environment]

    def form(self, invoice, attempt) -> dict[str, str]:
        if not self.enabled:
            raise RuntimeError("SePay credentials or IPN verification key are not configured")
        base_url = str(self.settings.public_base_url).rstrip("/")
        fields: dict[str, str] = OrderedDict((
            ("order_amount", str(attempt.amount)),
            ("merchant", self.settings.sepay_merchant_id),
            ("currency", "VND"),
            ("operation", "PURCHASE"),
            ("order_description", f"Thanh toan hoa don {invoice.invoice_code}"),
            ("order_invoice_number", attempt.order_id),
            ("payment_method", "BANK_TRANSFER"),
            ("success_url", f"{base_url}/public/v1/payments/sepay/return?result=success"),
            ("error_url", f"{base_url}/public/v1/payments/sepay/return?result=error"),
            ("cancel_url", f"{base_url}/public/v1/payments/sepay/return?result=cancel"),
        ))
        fields["signature"] = sign_fields(fields, self.settings.sepay_secret_key.get_secret_value())
        return fields

    def verify_ipn(self, candidate: str | None) -> bool:
        expected = self.settings.sepay_ipn_secret_key.get_secret_value()
        return bool(self.enabled and candidate and hmac.compare_digest(candidate, expected))

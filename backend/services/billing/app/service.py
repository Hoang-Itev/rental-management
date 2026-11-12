"""P08: calculation facade. Persistence, HTTP and issuance belong to P09."""
from __future__ import annotations
from typing import Mapping
from app.calculator import calculate_invoice
from app.schemas import InvoiceCalculationInput, InvoiceCalculationResult


class BillingCalculatorService:
    def calculate(self, payload: InvoiceCalculationInput | Mapping[str, object]) -> InvoiceCalculationResult:
        """Run deterministic, database-independent VND calculation."""
        return calculate_invoice(payload)

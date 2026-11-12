from datetime import date, timedelta
from types import SimpleNamespace

import pytest

from app.reminders import reminder_reason

TODAY = date(2026, 11, 12)


@pytest.mark.parametrize(("status", "days_overdue", "total", "expected"), [
    ("ISSUED", 1, 10000, "OUTSTANDING"),
    ("ISSUED", 0, 10000, "NOT_DUE"),
    ("ISSUED", -1, 10000, "NOT_DUE"),
    ("ISSUED", 1, 0, "NOT_DUE"),
    ("PAID", 2, 10000, "ALREADY_PAID"),
    ("VOID", 2, 10000, "VOID"),
    ("DRAFT", 2, 10000, "NOT_ISSUED"),
])
def test_reminder_eligibility(status, days_overdue, total, expected):
    invoice = SimpleNamespace(status=status, due_date=TODAY - timedelta(days=days_overdue), total_amount=total)
    assert reminder_reason(invoice, TODAY) == expected

"""P08 pure billing arithmetic: inclusive contract days, exclusive period_end.

Currency is integral VND. Round HALF_UP **per invoice item**, then sum items.
Day proration divides the *monthly* price by the calendar days in that month.
Term price changes create separate lines. No raw floats or implicit estimates.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import date
from decimal import Decimal, ROUND_HALF_UP, localcontext
from typing import Mapping

from app.schemas import (
    CalculatedLine,
    InvoiceCalculationInput,
    InvoiceCalculationResult,
    TermSnapshot,
    UsageSnapshot,
)

VND_QUANTUM = Decimal("1")
PRICE_QUANTUM = Decimal("0.0001")
QUANTITY_QUANTUM = Decimal("0.001")
MAX_BIGINT = 9_223_372_036_854_775_807
MAX_UNIT_PRICE = Decimal("99999999999999.9999")  # NUMERIC(18,4)
MAX_QUANTITY = Decimal("9999999999999.999")  # NUMERIC(16,3)


class CalculationError(ValueError):
    """Expected business-data error; code can become a P09 blocked_reason."""

    def __init__(self, code: str, message: str):
        self.code = code
        super().__init__(message)


def round_vnd(value: Decimal) -> int:
    """No Python round()/banker's rounding; input must be exact Decimal."""
    if not isinstance(value, Decimal) or not value.is_finite():
        raise CalculationError("INVALID_AMOUNT", "VND arithmetic requires a finite Decimal")
    if value < 0:
        raise CalculationError("NEGATIVE_AMOUNT", "invoice charges cannot be negative")
    with localcontext() as ctx:
        ctx.prec = 64
        rounded = int(value.quantize(VND_QUANTUM, rounding=ROUND_HALF_UP))
    if rounded > MAX_BIGINT:
        raise CalculationError("AMOUNT_OVERFLOW", "VND amount exceeds BIGINT")
    return rounded


def first_day_next_month(day: date) -> date:
    if day.month == 12:
        return date(day.year + 1, 1, 1)
    return date(day.year, day.month + 1, 1)


def _display_price(value: Decimal) -> Decimal:
    if value < 0 or not value.is_finite() or value > MAX_UNIT_PRICE:
        raise CalculationError("UNIT_PRICE_OVERFLOW", "unit price does not fit NUMERIC(18,4)")
    with localcontext() as ctx:
        ctx.prec = 64
        return value.quantize(PRICE_QUANTUM, rounding=ROUND_HALF_UP)


def _term_for(terms: list[TermSnapshot], day: date) -> TermSnapshot:
    active = [
        term for term in terms
        if term.effective_from <= day
        and (term.effective_to is None or day < term.effective_to)
    ]
    if len(active) != 1:
        raise CalculationError("TERM_COVERAGE", f"expected one active term on {day}, got {len(active)}")
    return active[0]


def _term_segments(request: InvoiceCalculationInput):
    """Yield (start,end,term,days_in_calendar_month), without losing leap days."""
    terms = sorted(request.terms, key=lambda x: x.effective_from)
    for a, b in zip(terms, terms[1:]):
        if a.effective_to is None or a.effective_to > b.effective_from:
            raise CalculationError("OVERLAPPING_TERMS", "contract terms overlap")
    cursor = request.period_start
    while cursor < request.period_end:
        term = _term_for(terms, cursor)
        month_end = first_day_next_month(cursor)
        stop = min(
            request.period_end,
            month_end,
            term.effective_to if term.effective_to is not None else request.period_end,
        )
        if stop <= cursor:
            raise CalculationError("TERM_COVERAGE", "contract term has no billable days")
        month_start = date(cursor.year, cursor.month, 1)
        yield cursor, stop, term, (month_end - month_start).days
        cursor = stop


def _daily_line(kind: str, start: date, end: date, term: TermSnapshot,
                month_days: int, monthly_amount: int) -> CalculatedLine:
    days = (end - start).days
    with localcontext() as ctx:
        ctx.prec = 64
        raw_daily_rate = Decimal(monthly_amount) / Decimal(month_days)
        raw_amount = Decimal(monthly_amount) * Decimal(days) / Decimal(month_days)
    amount = round_vnd(raw_amount)
    return CalculatedLine(
        item_type=kind, description=f"{kind.title()} {start.isoformat()}..{end.isoformat()} (end exclusive)",
        quantity=Decimal(days).quantize(QUANTITY_QUANTUM),
        unit="DAY", unit_price=_display_price(raw_daily_rate), amount=amount,
        period_start=start, period_end=end, source_term_id=term.id,
    )


def _utility_lines(request: InvoiceCalculationInput, terms: list[TermSnapshot]) -> list[CalculatedLine]:
    groups: dict[str, list[UsageSnapshot]] = defaultdict(list)
    for segment in request.usage_segments:
        groups[segment.meter_type].append(segment)
    if set(groups) != {"ELECTRICITY", "WATER"}:
        raise CalculationError("MISSING_METER", "both ELECTRICITY and WATER intervals are required")

    lines: list[CalculatedLine] = []
    for kind in ("ELECTRICITY", "WATER"):
        segments = sorted(groups[kind], key=lambda item: (item.period_start, item.period_end))
        meter_ids = {item.meter_id for item in segments}
        if len(meter_ids) != 1:
            raise CalculationError("METER_MISMATCH", f"{kind} intervals reference multiple meters")
        cursor = request.period_start
        previous: UsageSnapshot | None = None
        for item in segments:
            if item.period_start != cursor or item.period_end > request.period_end:
                raise CalculationError("USAGE_COVERAGE", f"{kind} usage gaps, overlap or out-of-period data")
            if previous is not None and (
                previous.end_reading != item.start_reading or
                previous.source_cutoff_end_id != item.source_cutoff_start_id
            ):
                raise CalculationError("USAGE_DISCONTINUITY", f"{kind} reading or cutoff boundary mismatch")

            term = _term_for(terms, item.period_start)
            if term.effective_to is not None and item.period_end > term.effective_to:
                raise CalculationError(
                    "PRICE_BOUNDARY_READING_REQUIRED",
                    f"{kind} interval crosses contract price change without intermediate confirmed cutoff",
                )
            price = (
                term.electricity_unit_price if kind == "ELECTRICITY"
                else term.water_unit_price
            )
            quantity = item.end_reading - item.start_reading
            if quantity > MAX_QUANTITY:
                raise CalculationError("QUANTITY_OVERFLOW", "meter consumption exceeds NUMERIC(16,3)")
            lines.append(CalculatedLine(
                item_type=kind,
                description=f"{kind.title()} {item.period_start.isoformat()}..{item.period_end.isoformat()}",
                quantity=quantity.quantize(QUANTITY_QUANTUM),
                unit="KWH" if kind == "ELECTRICITY" else "M3",
                unit_price=_display_price(Decimal(price)),
                amount=round_vnd(quantity * Decimal(price)),
                period_start=item.period_start, period_end=item.period_end,
                meter_start_value=item.start_reading,
                meter_end_value=item.end_reading,
                source_term_id=term.id,
                source_cutoff_start_id=item.source_cutoff_start_id,
                source_cutoff_end_id=item.source_cutoff_end_id,
            ))
            cursor = item.period_end
            previous = item
        if cursor != request.period_end:
            raise CalculationError("USAGE_COVERAGE", f"{kind} usage does not cover invoice period")
    return lines


def calculate_invoice(
    payload: InvoiceCalculationInput | Mapping[str, object],
) -> InvoiceCalculationResult:
    """Calculate immutable invoice_items snapshots; no database or network calls.

    Rent and monthly service fee are prorated per term/month; electricity/water
    use exact cumulative cutoff differences with the price active in that slice.
    P09 owns draft creation, missing-data handling, issuance and idempotency.
    """
    request = (
        payload if isinstance(payload, InvoiceCalculationInput)
        else InvoiceCalculationInput.model_validate(payload)
    )
    terms = sorted(request.terms, key=lambda x: x.effective_from)
    # Validate all terms and complete period coverage before computing any money.
    periods = list(_term_segments(request))
    items: list[CalculatedLine] = []
    for start, end, term, month_days in periods:
        items.append(_daily_line("RENT", start, end, term, month_days, term.monthly_rent))
        items.append(_daily_line("SERVICE", start, end, term, month_days, term.monthly_service_fee))
    items.extend(_utility_lines(request, terms))
    total = sum((item.amount for item in items), 0)
    if total > MAX_BIGINT:
        raise CalculationError("AMOUNT_OVERFLOW", "invoice total exceeds BIGINT")
    return InvoiceCalculationResult(
        period_start=request.period_start, period_end=request.period_end,
        items=items, total_amount=total,
    )

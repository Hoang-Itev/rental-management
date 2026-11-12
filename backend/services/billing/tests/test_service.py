"""P08: calendar-day proration, tariff versioning, accurate VND and cutoff audit."""
from __future__ import annotations

from copy import deepcopy
from datetime import date, timedelta
from decimal import Decimal
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.calculator import CalculationError, calculate_invoice, round_vnd
from app.schemas import InvoiceCalculationInput
from app.service import BillingCalculatorService


def term(start: date, end: date | None = None, *, rent=3_100_000,
         electricity=3_500, water=15_000, service=310_000):
    return {
        "id": uuid4(), "effective_from": start, "effective_to": end,
        "monthly_rent": rent, "electricity_unit_price": electricity,
        "water_unit_price": water, "monthly_service_fee": service,
    }


def segment(kind: str, start: date, end: date, *, a="100.000", b="105.123",
            meter_id=None, start_id=None, end_id=None):
    return {
        "meter_type": kind, "meter_id": meter_id or uuid4(),
        "period_start": start, "period_end": end,
        "source_cutoff_start_id": start_id or uuid4(),
        "source_cutoff_end_id": end_id or uuid4(),
        "start_cutoff_status": "CONFIRMED", "end_cutoff_status": "CONFIRMED",
        "start_reading": a, "end_reading": b,
    }


def payload(start: date = date(2026, 1, 1), end: date = date(2026, 2, 1),
            *, terms=None, electricity=None, water=None):
    return {
        "period_start": start, "period_end": end,
        "terms": terms if terms is not None else [term(start)],
        "usage_segments": [
            electricity if electricity is not None else segment("ELECTRICITY", start, end),
            water if water is not None else segment("WATER", start, end, a="20", b="21.250"),
        ],
    }


def charge(result, kind):
    return sum(line.amount for line in result.items if line.item_type == kind)


@pytest.mark.parametrize("start,end,days", [
    (date(2023, 2, 1), date(2023, 3, 1), 28),
    (date(2024, 2, 1), date(2024, 3, 1), 29),
    (date(2026, 4, 1), date(2026, 5, 1), 30),
    (date(2026, 1, 1), date(2026, 2, 1), 31),
])
def test_full_month_28_29_30_31_days(start, end, days):
    result = BillingCalculatorService().calculate(payload(start, end))
    assert (end - start).days == days
    assert charge(result, "RENT") == 3_100_000
    assert charge(result, "SERVICE") == 310_000
    assert charge(result, "ELECTRICITY") == 17_931  # 5.123 * 3500 -> 17930.5 HALF_UP
    assert charge(result, "WATER") == 18_750
    assert result.total_amount == 3_446_681
    assert result.total_amount == sum(line.amount for line in result.items)


def test_mid_month_start_prorates_rent_and_service_without_rounding_daily_rate():
    start, end = date(2026, 11, 15), date(2026, 12, 1)
    data = payload(start, end, terms=[term(start, rent=3_000_000, service=300_000)])
    result = calculate_invoice(data)
    assert charge(result, "RENT") == 1_600_000  # 16 / 30
    assert charge(result, "SERVICE") == 160_000
    line = next(x for x in result.items if x.item_type == "RENT")
    assert line.quantity == Decimal("16.000")
    assert line.unit_price == Decimal("100000.0000")


def test_proration_preserves_unrounded_monthly_value_for_vnd_line():
    start, end = date(2026, 1, 1), date(2026, 1, 16)
    result = calculate_invoice(payload(start, end, terms=[term(start, rent=1_000_001, service=0)]))
    line = next(x for x in result.items if x.item_type == "RENT")
    assert line.unit_price == Decimal("32258.0968")  # display-only 4dp
    assert line.amount == 483_871  # 1,000,001 * 15/31 rounded from ORIGINAL


def test_inclusive_contract_last_day_is_represented_by_exclusive_end():
    start, last_occupied = date(2026, 6, 13), date(2026, 6, 16)
    end = last_occupied + timedelta(days=1)
    result = calculate_invoice(payload(start, end, terms=[term(start, rent=300_000, service=0)]))
    assert next(x for x in result.items if x.item_type == "RENT").quantity == 4
    assert charge(result, "RENT") == 40_000


def test_cross_month_uses_each_calendar_month_denominator():
    start, end = date(2024, 2, 28), date(2024, 3, 3)
    result = calculate_invoice(payload(start, end))
    rental = [x for x in result.items if x.item_type == "RENT"]
    assert len(rental) == 2
    assert [x.quantity for x in rental] == [2, 2]  # Feb 28+29, Mar 1+2
    assert [x.amount for x in rental] == [213_793, 200_000]
    assert sum(x.amount for x in rental) == 413_793


def test_price_changed_midmonth_split_rent_service_and_meter_consumption():
    start, split, end = date(2026, 11, 1), date(2026, 11, 16), date(2026, 12, 1)
    terms = [
        term(start, split, rent=3_000_000, service=300_000, electricity=3_000, water=10_000),
        term(split, None, rent=6_000_000, service=600_000, electricity=4_000, water=20_000),
    ]
    e = uuid4(); w = uuid4()
    e0,e1,e2 = uuid4(),uuid4(),uuid4()
    w0,w1,w2 = uuid4(),uuid4(),uuid4()
    usages = [
        segment("ELECTRICITY", start, split, meter_id=e, a="100", b="105", start_id=e0, end_id=e1),
        segment("ELECTRICITY", split, end, meter_id=e, a="105", b="111", start_id=e1, end_id=e2),
        segment("WATER", start, split, meter_id=w, a="20", b="21", start_id=w0, end_id=w1),
        segment("WATER", split, end, meter_id=w, a="21", b="23", start_id=w1, end_id=w2),
    ]
    result = calculate_invoice({"period_start":start,"period_end":end,"terms":terms,"usage_segments":usages})
    assert charge(result, "RENT") == 4_500_000
    assert charge(result, "SERVICE") == 450_000
    assert charge(result, "ELECTRICITY") == 39_000  # 5*3000 + 6*4000
    assert charge(result, "WATER") == 50_000  # 1*10000 + 2*20000
    assert result.total_amount == 5_039_000
    assert [x.source_term_id for x in result.items if x.item_type == "ELECTRICITY"] == [terms[0]["id"],terms[1]["id"]]
    assert all(x.source_cutoff_start_id for x in result.items if x.item_type in {"ELECTRICITY","WATER"})


def test_price_change_without_cutoff_on_boundary_is_rejected_not_estimated():
    start, split, end = date(2026, 11, 1), date(2026, 11, 16), date(2026, 12, 1)
    data = payload(start,end,terms=[term(start,split),term(split)])
    with pytest.raises(CalculationError,match="price change") as err:
        calculate_invoice(data)
    assert err.value.code == "PRICE_BOUNDARY_READING_REQUIRED"


def test_term_gap_in_coverage_is_rejected():
    start, mid, end = date(2026,11,1),date(2026,11,10),date(2026,12,1)
    data=payload(start,end,terms=[term(start,mid),term(mid+timedelta(days=1))])
    with pytest.raises(CalculationError) as e:calculate_invoice(data)
    assert e.value.code == "TERM_COVERAGE"


def test_term_overlap_is_rejected():
    start,end=date(2026,11,1),date(2026,12,1)
    data=payload(start,end,terms=[term(start,date(2026,11,20)),term(date(2026,11,15))])
    with pytest.raises(CalculationError) as e:calculate_invoice(data)
    assert e.value.code == "OVERLAPPING_TERMS"


def test_no_term_on_invoice_start_is_rejected():
    start,end=date(2026,11,1),date(2026,12,1)
    data=payload(start,end,terms=[term(date(2026,11,2))])
    with pytest.raises(CalculationError) as e:calculate_invoice(data)
    assert e.value.code == "TERM_COVERAGE"


def test_missing_water_and_meter_id_mismatch_are_rejected():
    data=payload(); data["usage_segments"]=[data["usage_segments"][0]]
    with pytest.raises(ValidationError): calculate_invoice(data)  # schema requires >=2
    data=payload(); data["usage_segments"]=[data["usage_segments"][0]]*2
    with pytest.raises(CalculationError) as e:calculate_invoice(data)
    assert e.value.code == "MISSING_METER"
    data=payload()
    e=deepcopy(data["usage_segments"][0]); split=date(2026,1,16)
    e["period_end"]=split; e["end_reading"]="103"
    e2=deepcopy(e);e2.update(period_start=split,period_end=date(2026,2,1),start_reading="103", end_reading="105.123",source_cutoff_start_id=e["source_cutoff_end_id"], meter_id=uuid4())
    data["usage_segments"]=[e,e2,data["usage_segments"][1]]
    with pytest.raises(CalculationError) as e:calculate_invoice(data)
    assert e.value.code == "METER_MISMATCH"


@pytest.mark.parametrize("offset", [1,-1])
def test_usage_overlap_or_gap_is_rejected(offset):
    data=payload();e=data["usage_segments"][0];split=date(2026,1,15)
    a={**e,"period_end":split,"end_reading":"103"}
    b={**e,"period_start":split+timedelta(days=offset),"start_reading":"103","source_cutoff_start_id":a["source_cutoff_end_id"]}
    data["usage_segments"]=[a,b,data["usage_segments"][1]]
    with pytest.raises(CalculationError) as err:calculate_invoice(data)
    assert err.value.code == "USAGE_COVERAGE"


def test_missing_end_of_usage_is_rejected():
    data=payload();data["usage_segments"][0]["period_end"]=date(2026,1,20)
    with pytest.raises(CalculationError) as err:calculate_invoice(data)
    assert err.value.code == "USAGE_COVERAGE"


@pytest.mark.parametrize("field", ["start_reading","source_cutoff_start_id"])
def test_consumption_chain_must_be_continuous(field):
    data=payload();e=data["usage_segments"][0];split=date(2026,1,16)
    a={**e,"period_end":split,"end_reading":"103"}
    b={**e,"period_start":split,"start_reading":"103","source_cutoff_start_id":a["source_cutoff_end_id"]}
    b[field]="102" if field=="start_reading" else uuid4()
    data["usage_segments"]=[a,b,data["usage_segments"][1]]
    with pytest.raises(CalculationError) as err:calculate_invoice(data)
    assert err.value.code == "USAGE_DISCONTINUITY"


def test_negative_cumulative_delta_is_not_clamped():
    data=payload();data["usage_segments"][0]["end_reading"]="99.999"
    with pytest.raises(ValidationError,match="decreased"):calculate_invoice(data)


def test_invalid_meter_precision_and_float_are_rejected():
    data=payload();data["usage_segments"][0]["end_reading"]="105.1234"
    with pytest.raises(ValidationError):calculate_invoice(data)
    data=payload();data["usage_segments"][0]["end_reading"]=105.123
    with pytest.raises(ValidationError,match="never float"):calculate_invoice(data)


def test_pending_or_superseded_cutoffs_cannot_be_billed():
    for status in ["PENDING","SUPERSEDED"]:
        data=payload();data["usage_segments"][0]["end_cutoff_status"]=status
        with pytest.raises(ValidationError):calculate_invoice(data)


def test_reading_halves_round_up_at_exact_vnd_half():
    data=payload()
    data["usage_segments"][0].update(start_reading="100",end_reading="100.500")
    data["terms"][0]["electricity_unit_price"]=1
    result=calculate_invoice(data)
    assert charge(result,"ELECTRICITY")==1
    assert round_vnd(Decimal("0.49")) == 0
    assert round_vnd(Decimal("0.50")) == 1
    assert round_vnd(Decimal("1.50")) == 2


def test_line_rounding_then_sum_not_global_rounding():
    start,split,end=date(2026,11,1),date(2026,11,16),date(2026,12,1)
    terms=[term(start,split,rent=1,service=0),term(split,rent=1,service=0)]
    e=uuid4();w=uuid4();id1=uuid4();id2=uuid4()
    usages=[segment("ELECTRICITY",start,split, a="0",b="0",meter_id=e,end_id=id1),
        segment("ELECTRICITY",split,end,a="0",b="0",meter_id=e,start_id=id1),
        segment("WATER",start,split,a="0",b="0",meter_id=w,end_id=id2),
        segment("WATER",split,end,a="0",b="0",meter_id=w,start_id=id2)]
    result=calculate_invoice({"period_start":start,"period_end":end,"terms":terms,"usage_segments":usages})
    assert [x.amount for x in result.items if x.item_type=="RENT"]==[1,1]
    assert charge(result,"RENT")==2


def test_price_or_amount_overflow_is_rejected():
    with pytest.raises(CalculationError) as err:round_vnd(Decimal("9223372036854775807.5"))
    assert err.value.code=="AMOUNT_OVERFLOW"
    data=payload();data["terms"][0]["monthly_rent"]=9_223_372_036_854_775_807
    with pytest.raises(CalculationError) as err:calculate_invoice(data)
    assert err.value.code=="UNIT_PRICE_OVERFLOW"


def test_round_vnd_rejects_non_decimal_negative_nan():
    for value in [1.5,Decimal("NaN")]:
        with pytest.raises(CalculationError) as err:round_vnd(value)
        assert err.value.code=="INVALID_AMOUNT"
    with pytest.raises(CalculationError) as err:round_vnd(Decimal("-1"))
    assert err.value.code=="NEGATIVE_AMOUNT"


def test_schema_rejects_invalid_dates_and_extra_fields():
    data=payload();data["period_end"]=data["period_start"]
    with pytest.raises(ValidationError):InvoiceCalculationInput.model_validate(data)
    data=payload();data["terms"][0]["effective_to"]=data["terms"][0]["effective_from"]
    with pytest.raises(ValidationError):InvoiceCalculationInput.model_validate(data)
    data=payload();data["unknown_extra"]=True
    with pytest.raises(ValidationError):InvoiceCalculationInput.model_validate(data)
    data=payload();data["usage_segments"][0]["period_end"]=data["usage_segments"][0]["period_start"]
    with pytest.raises(ValidationError):InvoiceCalculationInput.model_validate(data)
    data=payload();data["terms"][0]["monthly_rent"]=1.5
    with pytest.raises(ValidationError):InvoiceCalculationInput.model_validate(data)


def test_service_and_calculator_same_repeatable_output_json():
    data=payload()
    one=BillingCalculatorService().calculate(data)
    two=calculate_invoice(InvoiceCalculationInput.model_validate(data))
    assert one == two
    assert one.model_dump(mode="json") == two.model_dump(mode="json")
    assert {line.item_type for line in one.items} == {"RENT", "SERVICE", "ELECTRICITY", "WATER"}
    assert next(x for x in one.items if x.item_type=="ELECTRICITY").quantity == Decimal("5.123")

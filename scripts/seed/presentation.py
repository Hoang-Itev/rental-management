"""Local presentation fixtures; real calculator, no fabricated payments or SENT jobs.

The PowerShell runner pins SEED_AS_OF so repeated runs retain the same identities.
Run with workers stopped; activate workers only after seed verification finishes.
"""
from datetime import date, timedelta
from decimal import Decimal

from seed_service import add_if_missing, delta_meter_value, initial_meter_value, midnight_vn, money_for_room, sid, VN

RECIPIENTS = (
    'n23dccn089@student.ptithcm.edu.vn',
    'n23dccn086@student.ptithcm.edu.vn',
    'n23dccn090@student.ptithcm.edu.vn',
    'hoangdv955@gmail.com',
)


def build_dataset(as_of: date) -> dict:
    current = (as_of - timedelta(days=11)).replace(day=1)
    previous = (current - timedelta(days=1)).replace(day=1)
    rooms = [f'{building}{floor}0{number}' for building in 'AB' for floor in (1, 2) for number in range(1, 6)]
    issued, blocked = rooms[:12], rooms[12:14]
    final_room, expiring_room = rooms[14:16]
    tenants = [dict(name=f'Khách demo {i+1:02d}', email=RECIPIENTS[i % 4]) for i in range(18)]
    contracts = []
    for i, room in enumerate(issued + blocked):
        contracts.append(dict(code=f'DEMO-CT-{i+1:03d}', room_code=room, tenant_index=i,
                              start_date=previous.isoformat(),
                              end_date=(current.replace(year=current.year+1)-timedelta(days=1)).isoformat(),
                              status='ACTIVE'))
    final_end = as_of - timedelta(days=2)
    contracts.append(dict(code='DEMO-CT-FINAL', room_code=final_room, tenant_index=14,
                          start_date=final_end.replace(day=1).isoformat(), end_date=final_end.isoformat(),
                          actual_end_date=final_end.isoformat(), status='ENDED'))
    contracts.append(dict(code='DEMO-CT-EXPIRING', room_code=expiring_room, tenant_index=15,
                          start_date=as_of.replace(day=1).isoformat(), end_date=(as_of+timedelta(days=5)).isoformat(),
                          status='ACTIVE'))
    return dict(version='presentation_v1', as_of=as_of.isoformat(),
                property=dict(code='DEMO-PRESENTATION', name='Nhà trọ Demo Thuyết Trình', address='TP. Hồ Chí Minh'),
                buildings=[dict(code=b, name=f'Dãy {b}') for b in 'AB'], rooms=rooms,
                occupied_rooms=issued+blocked+[expiring_room], tenants=tenants, contracts=contracts,
                issued_rooms=issued, blocked_rooms=blocked, final_room=final_room, expiring_room=expiring_room,
                billing_month=previous.isoformat(), period_end=current.isoformat(),
                # _issue() grants 10 days; these invoices were issued 11 days before demo day.
                issued_day=(as_of-timedelta(days=11)).isoformat(),
                invoice_due_date=(as_of-timedelta(days=1)).isoformat())


def meter_value(code, kind, day, data):
    """A monotone historical series with exactly the documented closed-month usage."""
    start, end = map(date.fromisoformat, (data['billing_month'], data['period_end']))
    days = Decimal((day-start).days)
    return (initial_meter_value(code, kind, data) + delta_meter_value(code, kind, data)
            * days / Decimal((end-start).days)).quantize(Decimal('0.001'))


def cutoff_plan(code, data):
    """One physical boundary, optionally shared by monthly and handover reasons."""
    contract = next((c for c in data['contracts'] if c['room_code'] == code), None)
    if contract is None:
        return []
    start = date.fromisoformat(contract['start_date'])
    monthly_start = date.fromisoformat(data['billing_month'])
    monthly_end = date.fromisoformat(data['period_end'])
    plans = {}
    if contract['status'] != 'ENDED':
        for day in (monthly_start, monthly_end):
            if day >= start:
                plans[day] = dict(day=day, kind='MONTHLY', pending=code in data['blocked_rooms'] and day==monthly_end, reasons=[])
    plans.setdefault(start, dict(day=start, kind='CONTRACT_START', pending=False, reasons=[]))['reasons'].append('CONTRACT_START')
    if contract.get('actual_end_date'):
        end = date.fromisoformat(contract['actual_end_date'])+timedelta(days=1)
        plans[end] = dict(day=end, kind='CONTRACT_END', pending=True, reasons=['CONTRACT_END'])
    return sorted(plans.values(), key=lambda p: p['day'])


def seed_metering(session, m, data):
    count = 0
    first = date.fromisoformat(data['billing_month'])
    today = date.fromisoformat(data['as_of'])
    for code in data['rooms']:
        contract = next((c for c in data['contracts'] if c['room_code']==code), None)
        plans = cutoff_plan(code, data)
        for kind, unit in (('ELECTRICITY', 'KWH'), ('WATER', 'M3')):
            mid = sid('meter', f'{code}:{kind}')
            count += add_if_missing(session, m.Meter, id=mid, room_id=sid('room', code),
                                    meter_code=f'DEMO-{code}-{kind[0]}', meter_type=kind, unit=unit,
                                    initial_reading=initial_meter_value(code, kind, data), status='ACTIVE',
                                    last_received_at=midnight_vn(today.isoformat()))
            missing = {p['day'] for p in plans if p['pending']}
            # Historical midnight samples, skipping deliberately missing boundaries.
            for offset in range((today-first).days+1):
                day = first+timedelta(days=offset)
                if day in missing:
                    continue
                stamp = midnight_vn(day.isoformat())
                pk = dict(meter_id=mid, measured_at=stamp)
                if session.get(m.MeterReading, pk) is None:
                    session.add(m.MeterReading(**pk, reading_value=meter_value(code,kind,day,data),
                                              validation_status='VALID', received_at=stamp))
                    session.flush()
                    count += 1
            for plan in plans:
                day = plan['day']
                cid = sid('cutoff', f'{code}:{kind}:{day.isoformat()}')
                pending = plan['pending']
                stamp = midnight_vn(day.isoformat())
                count += add_if_missing(session, m.MeterCutoff, id=cid, meter_id=mid,
                                        contract_id=sid('contract',contract['code']) if plan['reasons'] else None,
                                        cutoff_type=plan['kind'], cutoff_at=stamp,
                                        reading_value=None if pending else meter_value(code,kind,day,data),
                                        source='AUTOMATIC', status='PENDING' if pending else 'CONFIRMED',
                                        source_reading_at=None if pending else stamp,
                                        confirmed_at=None if pending else stamp)
                for reason in plan['reasons']:
                    count += add_if_missing(session, m.MeterCutoffReason,
                                            id=sid('cutoff_reason',f'{cid}:{reason}'),cutoff_id=cid,
                                            contract_id=sid('contract',contract['code']), reason_type=reason)
    return count


def invoice_calculation(contract, data):
    from app.calculator import calculate_invoice
    from app.schemas import InvoiceCalculationInput, TermSnapshot, UsageSnapshot
    code = contract['room_code']
    start, end = map(date.fromisoformat, (data['billing_month'],data['period_end']))
    term = TermSnapshot(id=sid('term',contract['code']), effective_from=date.fromisoformat(contract['start_date']),
                        monthly_rent=money_for_room(code,data), electricity_unit_price=3500,
                        water_unit_price=15000, monthly_service_fee=100000)
    segments = [UsageSnapshot(meter_type=kind, meter_id=sid('meter',f'{code}:{kind}'),
                             period_start=start,period_end=end,
                             source_cutoff_start_id=sid('cutoff',f'{code}:{kind}:{start.isoformat()}'),
                             source_cutoff_end_id=sid('cutoff',f'{code}:{kind}:{end.isoformat()}'),
                             start_cutoff_status='CONFIRMED',end_cutoff_status='CONFIRMED',
                             start_reading=meter_value(code,kind,start,data),end_reading=meter_value(code,kind,end,data))
                for kind in ('ELECTRICITY','WATER')]
    return calculate_invoice(InvoiceCalculationInput(period_start=start,period_end=end,terms=[term],usage_segments=segments))


def seed_billing(session, m, data):
    count = 0
    for contract in data['contracts']:
        code = contract['room_code']
        if code == data['expiring_room']:
            continue  # Current-month contract, not yet due for monthly billing.
        final = code == data['final_room']
        blocked = code in data['blocked_rooms'] or final
        start = date.fromisoformat(contract['start_date'] if final else data['billing_month'])
        end = (date.fromisoformat(contract['actual_end_date'])+timedelta(days=1)) if final else date.fromisoformat(data['period_end'])
        result = None if blocked else invoice_calculation(contract, data)
        inv_id = sid('invoice',contract['code'])
        tenant = data['tenants'][contract['tenant_index']]
        count += add_if_missing(session, m.Invoice, id=inv_id, invoice_code=f'DEMO-{"FINAL" if final else "INV"}-{code}-{start:%Y%m}',
                                contract_id=sid('contract',contract['code']),room_id=sid('room',code),
                                invoice_type='FINAL' if final else 'PERIODIC',billing_month=None if final else start,
                                period_start=start, period_end=end,status='DRAFT' if blocked else 'ISSUED',
                                blocked_reason='PENDING_CUTOFF' if blocked else None, revision=1,
                                total_amount=0 if blocked else result.total_amount,
                                due_date=date.fromisoformat(data['invoice_due_date']),
                                issued_at=None if blocked else midnight_vn(data['issued_day']),
                                tenant_name_snapshot=tenant['name'],tenant_email_snapshot=tenant['email'],room_code_snapshot=code)
        for i,line in enumerate(result.items if result else []):
            count += add_if_missing(session,m.InvoiceItem,id=sid('invoice_item',f'{contract["code"]}:{i}'),
                                    invoice_id=inv_id,**line.model_dump())
    return count


def queue_reminders(session, m, data):
    """Use the real reminder rule and dedupe key; workers later perform actual delivery."""
    from app.reminders import enqueue_reminder, reminder_reason
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc)
    count = 0
    for contract in data['contracts']:
        if contract['room_code'] not in data['issued_rooms']:
            continue
        invoice = session.get(m.Invoice,sid('invoice',contract['code']))
        if invoice is None:
            raise RuntimeError('Seed Billing and verify before queueing reminders')
        if reminder_reason(invoice,now.astimezone(VN).date()) == 'OUTSTANDING':
            count += enqueue_reminder(session,invoice,now)
    print(f'[mail] {count} new reminder events; duplicates for the same invoice/day skipped')
    return count


if __name__ == '__main__':
    from seed_service import dataset
    data = dataset()
    if data['version'] != 'presentation_v1':
        raise SystemExit('Use SEED_PROFILE=presentation and the pinned SEED_AS_OF')
    print(f"Demo date: {data['as_of']}; invoice period: {data['billing_month']} .. {data['period_end']} (end exclusive)")
    for code in data['blocked_rooms'] + [data['final_room']]:
        for kind in ('ELECTRICITY','WATER'):
            for plan in cutoff_plan(code,data):
                if plan['pending']:
                    print(f"{code} {kind} {plan['kind']} cutoff_id={sid('cutoff',f'{code}:{kind}:{plan['day'].isoformat()}')} "
                          f"reading_value={meter_value(code,kind,plan['day'],data)}")

"""Read-only verification before starting workers or paying demo invoices."""
from collections import Counter
from datetime import date
from sqlalchemy import select, func
from seed_service import sid, money_for_room, delta_meter_value
from presentation import RECIPIENTS, cutoff_plan, meter_value


def check_presentation(session, m, data, service):
    if service == 'room':
        for code in data['rooms']:
            room = session.get(m.Room,sid('room',code))
            assert room and room.room_code == code
            assert (room.occupancy_contract_id is not None) == (code in data['occupied_rooms'])
        print('[verify] room: 20 rooms, 15 occupied, 5 available (including handed-over B105)')
    elif service == 'tenant':
        for c in data['contracts']:
            contract = session.get(m.Contract,sid('contract',c['code']))
            assert contract and contract.status == c['status']
            assert contract.start_date.isoformat() == c['start_date']
            assert contract.end_date.isoformat() == c['end_date']
            tenant = session.get(m.Tenant,sid('tenant',str(c['tenant_index'])))
            assert tenant.email == data['tenants'][c['tenant_index']]['email']
            term = session.get(m.ContractTerm,sid('term',c['code']))
            assert term and term.effective_from == contract.start_date
            if c['status'] == 'ENDED':
                assert contract.actual_end_date.isoformat() == c['actual_end_date']
        print('[verify] tenant: 18 tenants, 15 ACTIVE + 1 ENDED; one expires in 5 days')
    elif service == 'metering':
        pending = 0
        for code in data['rooms']:
            for kind in ('ELECTRICITY','WATER'):
                meter = session.get(m.Meter,sid('meter',f'{code}:{kind}'))
                assert meter and meter.room_id == sid('room',code)
                readings = session.scalars(select(m.MeterReading).where(m.MeterReading.meter_id==meter.id)
                                          .order_by(m.MeterReading.measured_at)).all()
                assert readings and all(a.reading_value <= b.reading_value for a,b in zip(readings,readings[1:]))
                for plan in cutoff_plan(code,data):
                    cutoff = session.get(m.MeterCutoff,sid('cutoff',f'{code}:{kind}:{plan["day"].isoformat()}'))
                    assert cutoff and cutoff.status == ('PENDING' if plan['pending'] else 'CONFIRMED')
                    if plan['pending']:
                        pending += 1
                        assert cutoff.reading_value is None
                    else:
                        assert cutoff.reading_value == meter_value(code,kind,plan['day'],data)
                    for reason in plan['reasons']:
                        assert session.get(m.MeterCutoffReason,sid('cutoff_reason',f'{cutoff.id}:{reason}'))
        assert pending == 6
        print('[verify] metering: 40 meters, monotone historical readings; 6 PENDING cutoffs')
    elif service == 'billing':
        recipients = Counter()
        for c in data['contracts']:
            if c['room_code'] == data['expiring_room']:
                continue
            invoice = session.get(m.Invoice,sid('invoice',c['code']))
            assert invoice and invoice.contract_id == sid('contract',c['code'])
            lines = session.scalars(select(m.InvoiceItem).where(m.InvoiceItem.invoice_id==invoice.id)).all()
            assert invoice.total_amount == sum(line.amount for line in lines)
            if c['room_code'] in data['issued_rooms']:
                from presentation import invoice_calculation
                expected = invoice_calculation(c,data)
                assert invoice.status == 'ISSUED' and len(lines) == 4
                assert invoice.total_amount == expected.total_amount > 0
                assert invoice.total_amount == (money_for_room(c['room_code'],data) + 100000
                    + int(delta_meter_value(c['room_code'],'ELECTRICITY',data) * 3500)
                    + int(delta_meter_value(c['room_code'],'WATER',data) * 15000))
                assert invoice.due_date < date.fromisoformat(data['as_of'])
                assert invoice.issued_at.date() <= invoice.due_date
                assert invoice.paid_at is None
                assert invoice.tenant_email_snapshot == data['tenants'][c['tenant_index']]['email']
                recipients[invoice.tenant_email_snapshot] += 1
                for line in lines:
                    if line.item_type in ('ELECTRICITY','WATER'):
                        assert line.meter_end_value-line.meter_start_value == line.quantity
                        assert line.source_cutoff_start_id == sid('cutoff',f'{c["room_code"]}:{line.item_type}:{data["billing_month"]}')
                        assert line.source_cutoff_end_id == sid('cutoff',f'{c["room_code"]}:{line.item_type}:{data["period_end"]}')
            else:
                assert invoice.status == 'DRAFT' and invoice.blocked_reason == 'PENDING_CUTOFF' and not lines
        assert recipients == Counter({email:3 for email in RECIPIENTS})
        assert session.scalar(select(func.count()).select_from(m.PaymentAttempt)) == 0
        # A repeated seed may already have queued real reminder requests.
        assert session.scalar(select(func.count()).select_from(m.OutboxEvent).where(
            m.OutboxEvent.event_type != 'InvoiceReminderRequested')) == 0
        print('[verify] billing: 12 overdue ISSUED (3 per email), 2 periodic DRAFT + 1 FINAL DRAFT; no fake payments')
    elif service == 'notification':
        assert session.scalar(select(func.count()).select_from(m.EmailJob)) == 0
        print('[verify] notification: empty until real reminder events are consumed')

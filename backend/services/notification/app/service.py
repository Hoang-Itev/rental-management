from datetime import datetime, timedelta, timezone

from app import repository as repo
from app.clients import DeliveryFailure, InvoiceNotIssued


def record_invoice_event(sessions, event):
    with sessions.begin() as db:
        repo.insert_once(db, event, f"Hóa đơn {event.data.invoice_code}")


def record_payment_event(sessions, event):
    with sessions.begin() as db:
        repo.insert_once(db, event, f"Biên nhận {event.data.invoice_code}", email_type="PAYMENT_RECEIPT")


def receipt_body(data):
    return (
        f"Chào {data['tenant_name']},\n\n"
        f"Đã nhận thanh toán cho hóa đơn {data['invoice_code']} của phòng {data['room_code']}.\n"
        f"Số tiền: {data['paid_amount']:,} VND. Mã giao dịch MoMo: {data['provider_transaction_id']}.\n"
    )


def invoice_body(data, link):
    return (
        f"Chào {data['tenant_name']},\n\n"
        f"Hóa đơn {data['invoice_code']} của phòng {data['room_code']} đã được phát hành.\n"
        f"Kỳ tính phí từ {data['period_start']} đến trước {data['period_end_exclusive']}.\n"
        f"Tổng tiền: {data['total_amount']:,} VND. Hạn thanh toán: {data['due_date']}.\n\n"
        f"Xem hóa đơn: {link}\n"
    )


def send_next(sessions, billing, smtp, settings, *, clock=lambda: datetime.now(timezone.utc)):
    # Keep the row lock through bounded I/O. If the worker dies the transaction
    # rolls back. SMTP itself cannot guarantee exactly-once after acceptance.
    with sessions.begin() as db:
        job = repo.claim_due(db, clock())
        if job is None:
            return False
        job.attempt_count += 1
        job.next_attempt_at = None
        try:
            if job.email_type == "PAYMENT_RECEIPT":
                body = receipt_body(job.template_data)
            else:
                body = invoice_body(job.template_data, billing.access_link(job))
            job.provider_message_id = smtp.send(job, body)
        except InvoiceNotIssued:
            job.status = "SKIPPED"
            job.last_error = "INVOICE_NOT_ISSUED"
        except DeliveryFailure as exc:
            job.last_error = str(exc)
            if job.attempt_count >= settings.notification_max_attempts:
                job.status = "FAILED"
            else:
                delay = min(3600, settings.notification_retry_seconds * 2 ** (job.attempt_count - 1))
                job.next_attempt_at = clock() + timedelta(seconds=delay)
        else:
            job.status = "SENT"
            job.sent_at = clock()
            job.last_error = None
        return True


def reset_failed_job(job):
    if job.email_type not in ("INVOICE", "PAYMENT_RECEIPT") or job.status != "FAILED":
        return False
    job.status = "PENDING"
    job.attempt_count = 0
    job.next_attempt_at = None
    job.last_error = None
    return True

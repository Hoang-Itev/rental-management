import smtplib
import ssl
from email.message import EmailMessage

import httpx
from pydantic import AnyHttpUrl, TypeAdapter


class InvoiceNotIssued(Exception):
    pass


class DeliveryFailure(Exception):
    pass


class BillingClient:
    def __init__(self, http, settings):
        self.http = http
        self.settings = settings

    def access_link(self, job):
        base = str(self.settings.billing_url).rstrip("/")
        try:
            response = self.http.post(
                f"{base}/internal/v1/invoices/{job.invoice_id}/access-links",
                headers={"X-Service-Token": self.settings.service_token.get_secret_value()},
                json={"source_event_id": str(job.source_event_id), "recipient_email": job.recipient_email},
            )
            if response.status_code == 409 and response.json().get("code") == "INVOICE_NOT_ISSUED":
                raise InvoiceNotIssued
            response.raise_for_status()
            return str(TypeAdapter(AnyHttpUrl).validate_python(response.json()["url"]))
        except (httpx.HTTPError, ValueError, KeyError, TypeError, AttributeError) as exc:
            raise DeliveryFailure("Billing link unavailable") from exc


class SmtpClient:
    def __init__(self, settings):
        self.settings = settings

    def send(self, job, body):
        settings = self.settings
        message_id = f"<invoice.{job.id}@rental-management.local>"
        try:
            message = EmailMessage()
            message["From"] = settings.smtp_from
            message["To"] = job.recipient_email
            message["Subject"] = job.subject
            message["Message-ID"] = message_id
            message.set_content(body)
            context = ssl.create_default_context()
            arguments = (settings.smtp_host, settings.smtp_port)
            timeout = settings.notification_timeout_seconds
            if settings.smtp_security == "tls":
                connection = smtplib.SMTP_SSL(*arguments, timeout=timeout, context=context)
            else:
                connection = smtplib.SMTP(*arguments, timeout=timeout)
            try:
                if settings.smtp_security == "starttls":
                    connection.starttls(context=context)
                if settings.smtp_username:
                    connection.login(settings.smtp_username, settings.smtp_password.get_secret_value())
                connection.send_message(message)
            finally:
                connection.close()
        except (OSError, smtplib.SMTPException, ValueError) as exc:
            raise DeliveryFailure("SMTP delivery failed") from exc
        return message_id

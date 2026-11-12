import smtplib
import ssl
from email.message import EmailMessage

import httpx
from pydantic import AnyHttpUrl, TypeAdapter


class InvoiceNotIssued(Exception):
    def __init__(self, reason="INVOICE_NOT_ISSUED"):
        self.reason = reason
        super().__init__(reason)


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
            if response.status_code == 409:
                code = response.json().get("code")
                if code in ("INVOICE_NOT_ISSUED", "INVOICE_NOT_REMINDABLE"):
                    raise InvoiceNotIssued(code)
            response.raise_for_status()
            return str(TypeAdapter(AnyHttpUrl).validate_python(response.json()["url"]))
        except (httpx.HTTPError, ValueError, KeyError, TypeError, AttributeError) as exc:
            raise DeliveryFailure("Billing link unavailable") from exc


    def check_reminder(self, job):
        base = str(self.settings.billing_url).rstrip("/")
        try:
            response = self.http.get(
                f"{base}/internal/v1/invoices/{job.invoice_id}/reminder-eligibility",
                headers={"X-Service-Token": self.settings.service_token.get_secret_value()},
            )
            response.raise_for_status()
            result = response.json()
            if result["invoice_id"] != str(job.invoice_id) or type(result["eligible"]) is not bool:
                raise ValueError("Invalid reminder eligibility")
            reason = result["reason"]
            if result["eligible"] is True and reason == "OUTSTANDING":
                return
            if result["eligible"] is False and reason in ("ALREADY_PAID", "VOID", "NOT_ISSUED", "NOT_DUE"):
                raise InvoiceNotIssued(reason)
            raise ValueError("Invalid reminder eligibility")
        except (httpx.HTTPError, ValueError, KeyError, TypeError) as exc:
            raise DeliveryFailure("Billing reminder eligibility unavailable") from exc


class ContractNoLongerExpiring(Exception):
    pass


class TenantClient:
    def __init__(self, http, settings):
        self.http = http
        self.settings = settings

    def check_expiry(self, data):
        base = str(self.settings.tenant_url).rstrip("/")
        contract_id, end_date = data["contract_id"], data["end_date"]
        try:
            response = self.http.get(
                f"{base}/internal/v1/contracts/{contract_id}/expiry-notification-eligibility",
                params={"end_date": end_date},
                headers={"X-Service-Token": self.settings.service_token.get_secret_value()},
            )
            response.raise_for_status()
            result = response.json()
            if (result["contract_id"] != contract_id or result["end_date"] != end_date
                    or type(result["eligible"]) is not bool):
                raise ValueError("Invalid contract expiry eligibility")
        except (httpx.HTTPError, ValueError, KeyError, TypeError) as exc:
            raise DeliveryFailure("Tenant expiry eligibility unavailable") from exc
        if not result["eligible"]:
            raise ContractNoLongerExpiring


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

"""Service-token HTTP reads. Dependency failures are never treated as zero usage."""
from datetime import date
from uuid import UUID

import httpx

from app.schemas import BillingContext, UsageSnapshot


class DependencyUnavailable(Exception):
    pass


class MissingCutoff(Exception):
    pass


class BillingClients:
    def __init__(self, http: httpx.Client, settings):
        self.http = http
        self.settings = settings

    def _get(self, base, path, params=None):
        try:
            response = self.http.get(
                str(base).rstrip("/") + path, params=params,
                headers={"X-Service-Token": self.settings.service_token.get_secret_value()},
            )
            response.raise_for_status()
            data = response.json()
            if not isinstance(data, dict):
                raise ValueError("Expected an object")
            return data
        except (httpx.HTTPError, ValueError) as exc:
            raise DependencyUnavailable("Billing dependency unavailable") from exc

    def billable(self, start: date, end: date):
        seen = set()
        cursor = None
        while True:
            params = {"period_start": start.isoformat(), "period_end_exclusive": end.isoformat()}
            if cursor is not None:
                params["cursor"] = cursor
            data = self._get(self.settings.tenant_url, "/internal/v1/contracts/billable", params)
            try:
                ids = [UUID(item["contract_id"]) for item in data["items"]]
                next_cursor = data.get("next_cursor")
                if next_cursor is not None:
                    next_cursor = str(UUID(next_cursor))
                if len(set(ids)) != len(ids) or seen.intersection(ids) or (
                    next_cursor is not None and (not ids or next_cursor != str(ids[-1]))
                ):
                    raise ValueError("Invalid cursor page")
            except (KeyError, TypeError, ValueError) as exc:
                raise DependencyUnavailable("Invalid Tenant contract page") from exc
            seen.update(ids)
            yield from ids
            if next_cursor is None:
                return
            cursor = next_cursor

    def context(self, contract_id: UUID) -> BillingContext:
        data = self._get(self.settings.tenant_url, f"/internal/v1/contracts/{contract_id}/billing-context")
        try:
            result = BillingContext.model_validate(data)
            if result.contract_id != contract_id:
                raise ValueError("Unexpected contract ID")
            return result
        except ValueError as exc:
            raise DependencyUnavailable("Invalid Tenant billing context") from exc

    def usage(self, context: BillingContext, start: date, end: date) -> list[UsageSnapshot]:
        data = self._get(self.settings.metering_url, f"/internal/v1/rooms/{context.room_id}/usage", {
            "contract_id": str(context.contract_id),
            "period_start": start.isoformat(), "period_end_exclusive": end.isoformat(),
        })
        try:
            if (UUID(data["room_id"]) != context.room_id or UUID(data["contract_id"]) != context.contract_id
                    or date.fromisoformat(data["period_start"]) != start
                    or date.fromisoformat(data["period_end_exclusive"]) != end):
                raise ValueError("Unexpected usage scope")
            if data["status"] == "PENDING_CUTOFF":
                raise MissingCutoff()
            if data["status"] != "READY":
                raise ValueError("Unexpected usage status")
            utilities = data["utilities"]
            if len(utilities) != 2 or {line["meter_type"] for line in utilities} != {"ELECTRICITY", "WATER"}:
                raise ValueError("Incomplete utility response")
            return [UsageSnapshot(
                meter_id=line["meter_id"], meter_type=line["meter_type"],
                period_start=start, period_end=end,
                source_cutoff_start_id=line["start_cutoff_id"],
                source_cutoff_end_id=line["end_cutoff_id"],
                start_cutoff_status="CONFIRMED", end_cutoff_status="CONFIRMED",
                start_reading=line["start_reading"], end_reading=line["end_reading"],
            ) for line in utilities]
        except (KeyError, TypeError, ValueError) as exc:
            raise DependencyUnavailable("Invalid Metering usage response") from exc

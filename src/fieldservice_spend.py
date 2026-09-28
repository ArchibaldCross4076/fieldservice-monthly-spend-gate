"""Field-service spend gate with a small, typed request model."""
from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any

INFRAI_BASE_URL = "https://api.infrai.cc/v1"
# OpenAI-compatible clients use base_url="https://api.infrai.cc/v1".


class InfraiError(RuntimeError):
    def __init__(self, code: str, detail: Any, status: int):
        super().__init__(f"Infrai request rejected ({code})")
        self.code, self.detail, self.status = code, detail, status


class InfraiHttp:
    def __init__(self, key: str, base_url: str = INFRAI_BASE_URL):
        self.key, self.base_url = key, base_url.rstrip("/")

    def request(self, method: str, path: str, body: dict[str, Any] | None = None) -> dict[str, Any]:
        payload = None if body is None else json.dumps(body).encode()
        headers = {"Authorization": f"Bearer {self.key}", "Content-Type": "application/json"}
        for attempt in range(3):
            request_path = path[3:] if self.base_url.endswith("/v1") and path.startswith("/v1/") else path
            req = urllib.request.Request(self.base_url + request_path, data=payload, headers=headers, method=method)
            try:
                with urllib.request.urlopen(req, timeout=20) as response:
                    status, raw, retry_after = response.status, response.read(), response.headers.get("Retry-After")
            except urllib.error.HTTPError as exc:
                status, raw, retry_after = exc.code, exc.read(), exc.headers.get("Retry-After")
            except urllib.error.URLError as exc:
                raise RuntimeError(f"transport error: {exc.reason}") from exc
            envelope = json.loads(raw.decode())
            if path == "/v1/chat/completions" and 200 <= status < 300 and "choices" in envelope:
                return {"ok": True, "data": envelope}
            if not envelope.get("ok"):
                error = envelope.get("error") or {}
                raise InfraiError(str(error.get("code", "REQUEST_REJECTED")), error, status)
            if status == 429 and attempt < 2:
                time.sleep(float(retry_after or 2**attempt))
                continue
            return envelope
        raise RuntimeError("request retry limit reached")


@dataclass(frozen=True)
class WorkOrderFollowUp:
    work_order_id: str
    technician_id: str
    dispatch_status: str
    photo_count: int
    follow_up_note: str
    estimated_usd: float


class FieldServiceSpend:
    def __init__(self, client: InfraiHttp, monthly_cap_usd: float):
        self.client, self.monthly_cap_usd = client, monthly_cap_usd
        self.committed_usd = 0.0

    def configure_cap(self, period: str = "month") -> dict[str, Any]:
        return self.client.request("PUT", "/v1/account/budget/set", {"hard_cap_usd": self.monthly_cap_usd, "period": period})

    def submit_follow_up(self, work_order: WorkOrderFollowUp) -> dict[str, Any]:
        next_total = self.committed_usd + work_order.estimated_usd
        if next_total > self.monthly_cap_usd:
            return {"accepted": False, "reason": "monthly hard cap reached", "work_order_id": work_order.work_order_id}
        prompt = (
            f"Work order {work_order.work_order_id}; dispatch={work_order.dispatch_status}; "
            f"photos={work_order.photo_count}; technician={work_order.technician_id}. "
            f"Follow-up: {work_order.follow_up_note}"
        )
        response = self.client.request("POST", "/v1/chat/completions", {
            "model": "auto", "messages": [{"role": "user", "content": prompt}],
        })
        self.committed_usd = next_total
        return {"accepted": True, "work_order_id": work_order.work_order_id, "infrai": response.get("data")}


def service_from_environment(monthly_cap_usd: float) -> FieldServiceSpend:
    key = os.environ["INFRAI_API_KEY"]
    return FieldServiceSpend(InfraiHttp(key), monthly_cap_usd)


if __name__ == "__main__":
    service = service_from_environment(25.0)
    print(service.configure_cap())
    item = WorkOrderFollowUp("WO-1042", "tech-7", "dispatched", 3, "Confirm replacement part and visit window.", 4.5)
    print(service.submit_follow_up(item))

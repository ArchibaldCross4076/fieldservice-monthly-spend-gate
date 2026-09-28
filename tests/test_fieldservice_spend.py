import json
from unittest.mock import patch

from fieldservice_spend import FieldServiceSpend, InfraiHttp, WorkOrderFollowUp


class FakeClient:
    def __init__(self):
        self.calls = []

    def request(self, method, path, body=None):
        self.calls.append((method, path, body))
        return {"ok": True, "data": {"message": "queued"}}


def test_follow_up_over_cap_is_rejected_before_ai_call():
    client = FakeClient()
    service = FieldServiceSpend(client, monthly_cap_usd=10)
    service.committed_usd = 8
    result = service.submit_follow_up(WorkOrderFollowUp("WO-9", "tech-2", "waiting", 2, "Call customer", 3))
    assert result["accepted"] is False
    assert client.calls == []


def test_chat_accepts_openai_compatible_response():
    class Response:
        status = 200
        headers = {}

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            pass

        def read(self):
            return json.dumps({"choices": [{"message": {"content": "Ready"}}]}).encode()

    with patch("urllib.request.urlopen", return_value=Response()):
        result = InfraiHttp("test-key").request("POST", "/v1/chat/completions", {"model": "auto"})
    assert result["data"]["choices"][0]["message"]["content"] == "Ready"

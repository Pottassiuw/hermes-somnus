from __future__ import annotations

from somnus.reflect import ReflectRequest, Reflector, sanitize_response


def test_reflect_payload_is_bounded_and_read_only_by_default():
    request = ReflectRequest("Summarize the verified Helios changes", max_tokens=1200)
    payload = request.payload()
    assert payload["budget"] == "low"
    assert payload["max_tokens"] == 1200
    assert payload["include"]["facts"] == {}
    assert "tool_calls" not in payload["include"]
    assert payload["exclude_mental_models"] is True
    assert payload["fact_types"] == ["world", "experience", "observation"]
    assert payload["response_schema"]["type"] == "object"


def test_reflect_rejects_unbounded_or_invalid_requests():
    for kwargs in [{"budget": "paid"}, {"max_tokens": 64}, {"fact_types": ("mental_model",)}]:
        try:
            ReflectRequest("query", **kwargs).payload()
        except ValueError:
            pass
        else:
            raise AssertionError("invalid request was accepted")


def test_response_sanitization_omits_ids_and_secrets():
    response = sanitize_response({
        "structured_output": {"summary": "ok", "memory_id": "abc", "api_key": "secret"},
        "based_on": {"memories": [{"id": "m1", "text": "API_KEY=secret"}]},
    })
    assert response["structured_output"]["memory_id"] == "[ID_OMITTED]"
    assert response["structured_output"]["api_key"] == "[REDACTED]"
    assert response["based_on"]["memories"][0]["id"] == "[ID_OMITTED]"
    assert "secret" not in str(response)


class FakeReflectClient:
    def __init__(self):
        self.calls = []
    def request(self, method, path, *, query=None, payload=None):
        self.calls.append((method, path, payload))
        return {"structured_output": {"summary": "safe", "memory_id": "m1"}}


def test_reflector_uses_bank_scoped_endpoint_and_schema():
    client = FakeReflectClient()
    result = Reflector(client).run("repo-edp-helios", ReflectRequest("What changed?"))
    assert client.calls[0][0:2] == ("POST", "/v1/default/banks/repo-edp-helios/reflect")
    assert result["structured_output"]["memory_id"] == "[ID_OMITTED]"

"""CMN-C1-172 — ResponseFormatNode unit tests."""
from __future__ import annotations

import inspect
import json

from framework.schemas.agent_status import AgentStatus
from src.nodes.response_format_node import ResponseFormatNode


class TestResponseFormatNode:
    def setup_method(self):
        self.node = ResponseFormatNode()

    def test_execute_signature_is_state_only(self):
        params = list(inspect.signature(ResponseFormatNode.execute).parameters.keys())
        assert params[1] == "state"
        assert "config" not in params
        assert "_invoke_impl" not in ResponseFormatNode.__dict__

    def test_no_results_returns_japanese_message(self):
        result = self.node.execute({
            "filtered_results": "[]",
            "normalized_query": "test",
            "pii_redacted": False,
            "search_elapsed_ms": 5,
        })
        assert result["status"] == AgentStatus.SUCCESS
        assert result["result_count"] == 0
        assert "見つかりませんでした" in result["response"]

    def test_appi_advisory_always_present(self):
        raw = json.dumps([{"doc_id": "doc1", "score": 0.9, "snippet": "policy doc",
                           "path": "/var/data/doc1.txt", "source_type": "local"}])
        result = self.node.execute({
            "filtered_results": raw,
            "normalized_query": "policy",
            "pii_redacted": False,
            "search_elapsed_ms": 8,
        })
        assert result["status"] == AgentStatus.SUCCESS
        assert "APPI 2026 advisory" in result["response"]
        assert result["result_count"] == 1

    def test_credential_in_results_blocked(self):
        fake_key = "sk-" + "q" * 25
        raw = json.dumps([{"doc_id": "doc1", "score": 0.95, "snippet": f"token={fake_key}",
                           "path": "/var/data/doc1.txt", "source_type": "local"}])
        result = self.node.execute({
            "filtered_results": raw,
            "normalized_query": "token",
            "pii_redacted": False,
            "search_elapsed_ms": 5,
        })
        assert result["status"] == AgentStatus.ERROR
        assert fake_key not in result["response"]

    def test_skips_on_upstream_error(self):
        result = self.node.execute({"status": AgentStatus.ERROR.value, "error_log": ["upstream failed"]})
        assert result["status"] == AgentStatus.ERROR

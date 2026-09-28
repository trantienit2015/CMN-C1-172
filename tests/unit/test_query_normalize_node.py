"""CMN-C1-172 — QueryNormalizeNode unit tests."""
from __future__ import annotations

import inspect

from framework.schemas.agent_status import AgentStatus
from src.nodes.query_normalize_node import QueryNormalizeNode


class TestQueryNormalizeNode:
    def setup_method(self):
        self.node = QueryNormalizeNode()

    def test_execute_signature_is_state_only(self):
        sig = inspect.signature(QueryNormalizeNode.execute)
        params = list(sig.parameters.keys())
        assert params[1] == "state"
        assert "config" not in params
        assert "_invoke_impl" not in QueryNormalizeNode.__dict__

    def test_normal_english_query(self):
        result = self.node.execute({"user_input": "Osaka expansion Q3"})
        assert result["status"] == AgentStatus.SUCCESS
        assert result["normalized_query"] == "Osaka expansion Q3"
        assert result["query_language"] == "en"

    def test_japanese_query_detected(self):
        result = self.node.execute({"user_input": "大阪展開プランQ3"})
        assert result["status"] == AgentStatus.SUCCESS
        assert result["query_language"] == "ja"

    def test_query_too_short_is_error(self):
        result = self.node.execute({"user_input": "a"})
        assert result["status"] == AgentStatus.ERROR
        assert result["normalized_query"] == ""

    def test_credential_in_query_blocked(self):
        fake_key = "sk-" + "x" * 25
        result = self.node.execute({"user_input": f"find docs key={fake_key}"})
        assert result["status"] == AgentStatus.ERROR
        assert result["normalized_query"] == ""

    def test_html_is_stripped(self):
        result = self.node.execute({"user_input": "<b>search</b> term"})
        assert result["status"] == AgentStatus.SUCCESS
        assert "<b>" not in result["normalized_query"]

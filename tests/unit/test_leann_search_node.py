"""CMN-C1-172 — LeannSearchNode unit tests (search + access control + PII redaction)."""
from __future__ import annotations

import inspect
import json

from framework.schemas.agent_status import AgentStatus
from src.nodes.leann_search_node import LeannSearchNode


class TestLeannSearchNode:
    def setup_method(self):
        self.node = LeannSearchNode()

    def test_execute_signature_is_state_only(self):
        params = list(inspect.signature(LeannSearchNode.execute).parameters.keys())
        assert params[1] == "state"
        assert "config" not in params
        assert "_invoke_impl" not in LeannSearchNode.__dict__

    def test_normal_search_returns_results(self):
        result = self.node.execute({
            "normalized_query": "delivery delays",
            "input_context": {"corpus_path": "/tmp/test_idx", "user_id": "emp_001"},
        })
        assert result["status"] == AgentStatus.SUCCESS
        results = json.loads(result["raw_results"])
        assert isinstance(results, list)
        assert result["search_elapsed_ms"] >= 0
        filtered = json.loads(result["filtered_results"])
        assert isinstance(filtered, list)

    def test_empty_query_is_error(self):
        result = self.node.execute({"normalized_query": ""})
        assert result["status"] == AgentStatus.ERROR
        assert result["raw_results"] == "[]"

    def test_network_corpus_path_rejected(self):
        result = self.node.execute({
            "normalized_query": "test query",
            "input_context": {"corpus_path": "https://evil.example.com/index"},
        })
        assert result["status"] == AgentStatus.ERROR
        assert "SECURITY" in result["error_log"][0]

    def test_restricted_path_blocked_for_non_admin(self):
        # The synthetic LEANN service emits local docs under the corpus_path; use a
        # restricted corpus_path so the access-control filter removes the docs.
        result = self.node.execute({
            "normalized_query": "board minutes",
            "input_context": {"corpus_path": "/var/data/restricted", "user_id": "emp_001"},
        })
        assert result["status"] == AgentStatus.SUCCESS
        filtered = json.loads(result["filtered_results"])
        assert filtered == [], "Non-admin must not see /restricted/ documents"
        assert result["filtered_count"] == 0

    def test_restricted_path_allowed_for_admin(self):
        result = self.node.execute({
            "normalized_query": "board minutes",
            "input_context": {"corpus_path": "/var/data/restricted", "user_id": "admin_001"},
        })
        assert result["status"] == AgentStatus.SUCCESS
        filtered = json.loads(result["filtered_results"])
        assert len(filtered) > 0, "Admin must be able to access /restricted/ documents"

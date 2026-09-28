"""CMN-C1-172 — Security unit tests (S-1 trust gate + S-3 helpers).

S-1 is enforced by the framework's BaseNode.__call__ (not hand-rolled). A node
declares required_trust_level = TrustLevel.INTERNAL; an under-trusted caller is
blocked BEFORE execute() runs (status -> "error" string after the gate).
"""
from __future__ import annotations

from framework.schemas.agent_status import AgentStatus
from framework.schemas.trust_level import TrustLevel
from src.nodes.leann_search_node import LeannSearchNode
from src.nodes.query_normalize_node import QueryNormalizeNode
from src.nodes.response_format_node import ResponseFormatNode
from src.services.security_service import apply_s3_gate, detect_credentials

_NODES = (QueryNormalizeNode, LeannSearchNode, ResponseFormatNode)


class TestS1TrustGate:
    def test_all_nodes_require_internal(self):
        for node_cls in _NODES:
            assert node_cls.required_trust_level is TrustLevel.INTERNAL

    def test_no_node_uses_verified_internal(self):
        # Criterion #13: VERIFIED_INTERNAL is not a valid TrustLevel.
        assert not hasattr(TrustLevel, "VERIFIED_INTERNAL")

    def test_under_trusted_caller_blocked_before_execute(self):
        # Invoke via __call__ (the framework entry point) with an under-trusted caller.
        node = QueryNormalizeNode()
        result = node({"user_input": "Osaka expansion Q3", "caller_trust_level": TrustLevel.ANONYMOUS.value})
        assert result["status"] == AgentStatus.ERROR.value
        assert any("trust gate" in e.lower() for e in result.get("error_log", []))

    def test_internal_caller_allowed(self):
        node = QueryNormalizeNode()
        result = node({"user_input": "Osaka expansion Q3", "caller_trust_level": TrustLevel.INTERNAL.value})
        # passes the gate → execute() runs → success status (string after __call__)
        assert result["status"] == AgentStatus.SUCCESS


class TestS3Helpers:
    def test_detect_credentials(self):
        assert detect_credentials("sk-" + "a" * 25)
        assert not detect_credentials("a normal query")

    def test_apply_s3_gate_blocks_credentials(self):
        out = apply_s3_gate("here is a key sk-" + "b" * 25)
        assert "BLOCKER" in out

    def test_apply_s3_gate_passes_clean_text(self):
        clean = "normal output text"
        assert apply_s3_gate(clean) == clean

"""Integration tests — full compile() + invoke() over the 5-node backbone (CMN-C1-172)."""
from framework.schemas.agent_status import AgentStatus
from framework.schemas.invocation_context import InvocationContext
from framework.schemas.trust_level import TrustLevel
from src.graph.graph import EnterprisePrivateDocSearchAgent


def _agent():
    agent = EnterprisePrivateDocSearchAgent()
    agent.compile()
    return agent


def _ctx(trust=TrustLevel.INTERNAL):
    return InvocationContext(caller_trust_level=trust)


def _input_context():
    return {"corpus_path": "/var/data/leann_index", "user_id": "admin_1"}


def test_full_pipeline_success():
    result = _agent().invoke("契約書の検索", ctx=_ctx(), input_context=_input_context())
    assert result["status"] == AgentStatus.SUCCESS.value
    assert result["output"]


def test_backbone_order():
    result = _agent().invoke("契約書の検索", ctx=_ctx(), input_context=_input_context())
    history = result["node_history"]
    for node in (
        "InitializeNode",
        "QueryNormalizeNode",
        "LeannSearchNode",
        "ResponseFormatNode",
        "FinalizeNode",
    ):
        assert node in history, f"{node} missing from node_history: {history}"


def test_invalid_query_short_circuits():
    result = _agent().invoke("a", ctx=_ctx(), input_context=_input_context())
    assert result["status"] == AgentStatus.ERROR.value


def test_s1_trust_gate_blocks_anonymous():
    result = _agent().invoke(
        "契約書の検索", ctx=_ctx(TrustLevel.ANONYMOUS), input_context=_input_context()
    )
    assert result["status"] == AgentStatus.ERROR.value
    # The S-1 gate denies each node's execute() before it runs (BaseNode.__call__
    # still records the node name in node_history, but execute() never produced a
    # rendered response — post_process is skipped on the error route to finalize).
    assert not result.get("output"), "no rendered output when the S-1 gate denies the caller"


def test_s1_trust_gate_blocks_verified_external():
    result = _agent().invoke(
        "契約書の検索", ctx=_ctx(TrustLevel.VERIFIED_EXTERNAL), input_context=_input_context()
    )
    assert result["status"] == AgentStatus.ERROR.value

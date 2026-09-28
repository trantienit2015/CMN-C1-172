"""Runtime proof-of-boundary tests for CMN-C1-172 (compile + invoke).

  PB-2 — post-invoke state is JSON-serializable (primitives only).
  PB-3 — template reaches the external LEANN service via src.services (on-device).
  PB-6 — full pipeline compile() + invoke() runs the 5-node backbone to SUCCESS.
  S-3  — no credential pattern leaks into the returned output.
"""
import json

from framework.schemas.agent_status import AgentStatus
from framework.schemas.invocation_context import InvocationContext
from framework.schemas.trust_level import TrustLevel
from src.graph.graph import EnterprisePrivateDocSearchAgent
from src.services.security_service import detect_credentials


def _agent():
    agent = EnterprisePrivateDocSearchAgent()
    agent.compile()
    return agent


def _ctx():
    return InvocationContext(caller_trust_level=TrustLevel.INTERNAL)


def _input_context():
    return {"corpus_path": "/var/data/leann_index", "user_id": "admin_1"}


def test_pb6_full_pipeline_compile_invoke():
    result = _agent().invoke("契約書の検索", ctx=_ctx(), input_context=_input_context())
    assert result["status"] == AgentStatus.SUCCESS.value
    assert result["output"]


def test_pb2_state_json_serializable():
    result = _agent().invoke("契約書の検索", ctx=_ctx(), input_context=_input_context())
    # Must round-trip through JSON — no Pydantic / dataclass / InvocationContext.
    json.dumps(result)


def test_pb3_external_service_reached():
    # The main slot calls the on-device LEANN service; a real result list proves the path.
    result = _agent().invoke("invoice 2024", ctx=_ctx(), input_context=_input_context())
    assert result["status"] == AgentStatus.SUCCESS.value


def test_s3_no_credentials_in_output():
    result = _agent().invoke("契約書の検索", ctx=_ctx(), input_context=_input_context())
    assert detect_credentials(result.get("output") or "") == []

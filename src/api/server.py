"""CMN-C1-172 — Standalone HTTP entry point.

Adapter only — no business logic. Receives a request, provisions secrets via the
S-3 provider pattern (``secrets_factory`` + ``bound_secrets``), and delegates to
``agent.invoke(user_input, ctx=ctx)``. Trust level / caller id arrive on the
``InvocationContext``; the framework enforces the S-1 trust gate.
"""

from __future__ import annotations

import os
import secrets
from pathlib import Path
from typing import Any
from uuid import uuid4

import yaml
from fastapi import FastAPI, HTTPException, Request
from langgraph.checkpoint.memory import MemorySaver
from pydantic import BaseModel

from framework.schemas.invocation_context import InvocationContext
from framework.schemas.trust_level import TrustLevel
from framework.secrets.context import bound_secrets
from shared.secrets import factory as secrets_factory

from src.graph.graph import Graph

app = FastAPI(title="EnterprisePrivateDocSearchAgent")

# Runtime config, same config_dir / "config.yaml" convention AgentRegistry uses;
# an absent file is tolerated and yields {}. Without this the standalone entry point
# constructed the graph with no config at all, so no runtime parameter reached it on
# this path.
_CONFIG_PATH = Path(__file__).resolve().parents[2] / "config" / "config.yaml"
_config = yaml.safe_load(_CONFIG_PATH.read_text(encoding="utf-8")) or {} if _CONFIG_PATH.exists() else {}

agent = Graph(config=_config)
# memory_enabled / hitl.enabled need a checkpointer, or memory and interrupt()
# silently no-op on this path.
_hitl_enabled = agent.config.get("hitl", {}).get("enabled", False)
_needs_checkpointer = agent.config.get("memory_enabled") or _hitl_enabled
agent.compile(checkpointer=MemorySaver() if _needs_checkpointer else None)
agent.provision_secrets(secrets_factory(namespace="cmn", agent_name="cmn-c1-172"))


class InvokeRequest(BaseModel):
    input: str
    session_id: str = ""
    user_id: str = ""
    corpus_path: str = ""


def _bearer_matches(supplied: str, expected: str) -> bool:
    """Constant-time bearer comparison that is safe for non-ASCII header input."""
    return secrets.compare_digest(supplied.encode(), f"Bearer {expected}".encode())


def _resolve_standalone_trust(
    current: TrustLevel, authorization: str, invoke_auth_token: str | None, internal_runner_token: str | None
) -> TrustLevel:
    """Authenticate standalone callers without allowing external-token elevation.

    The STG runner credential is a distinct, CI-generated deployment credential. It is
    considered only for an anonymous caller and maps exactly to INTERNAL; the external
    token stays at VERIFIED_EXTERNAL. Middleware-established trust is never changed.
    """
    if current is not TrustLevel.ANONYMOUS:
        return current
    if internal_runner_token and _bearer_matches(authorization, internal_runner_token):
        return TrustLevel.INTERNAL
    if invoke_auth_token and _bearer_matches(authorization, invoke_auth_token):
        return TrustLevel.VERIFIED_EXTERNAL
    if internal_runner_token or invoke_auth_token:
        raise HTTPException(status_code=401, detail="Token is invalid or expired.")
    return TrustLevel.ANONYMOUS


@app.post("/invoke")
async def invoke(req: InvokeRequest, request: Request) -> dict[str, Any]:
    # This adapter is the entry-point auth boundary (the standalone equivalent of the
    # platform auth middleware). Both values are deployment-level caller credentials, not
    # agent secrets: no InvocationContext exists before this boundary, so ctx.secrets
    # cannot apply.
    trust = _resolve_standalone_trust(
        getattr(request.state, "trust_level", TrustLevel.ANONYMOUS),
        request.headers.get("authorization", ""),
        os.environ.get("INVOKE_AUTH_TOKEN"),
        os.environ.get("STG_INTERNAL_RUNNER_TOKEN"),
    )
    with bound_secrets(agent._secrets_provider):
        ctx = InvocationContext(
            session_id=req.session_id or str(uuid4()),
            caller_trust_level=trust,
            caller_id=getattr(request.state, "caller_id", ""),
        )
        input_context = {}
        if req.user_id:
            input_context["user_id"] = req.user_id
        if req.corpus_path:
            input_context["corpus_path"] = req.corpus_path
        result = agent.invoke(req.input, ctx=ctx, input_context=input_context)
    # The graph contract returns a mapping. Verify it at the boundary instead of
    # declaring the shape and trusting it: an unexpected result would otherwise
    # reach the caller as a malformed body.
    if not isinstance(result, dict):
        raise HTTPException(status_code=500, detail="Agent returned an unexpected result shape.")
    return result


@app.get("/health")
def health() -> dict[str, Any]:
    return {"status": "ok", "agent": "cmn-c1-172"}

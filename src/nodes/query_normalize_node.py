"""CMN-C1-172 — QueryNormalizeNode (pre_process slot).

Normalizes and validates the raw user query before LEANN search.

Node contract:
  - Extend FunctionNode; override execute(self, state) -> dict (no config param).
  - Return ONLY changed fields; set status to an AgentStatus.* enum.
  - S-1 trust gate is enforced by the framework (BaseNode.__call__) from the
    node's required_trust_level class variable — not hand-rolled here.
"""

from __future__ import annotations

import re
from typing import Any

from framework.nodes.function_node import FunctionNode
from shared.services.events import emitter
from shared.services.events.types import EventType
from framework.schemas.agent_status import AgentStatus
from framework.schemas.trust_level import TrustLevel
from shared.utils.audit_logger import emit_trace_event

from src.services.security_service import detect_credentials, sanitize_query

_MAX_QUERY_LEN = 512
_MIN_QUERY_LEN = 2


class QueryNormalizeNode(FunctionNode):
    """Normalize, validate, and language-detect the user query.

    Input:  user_input (the raw query)
    Output: normalized_query, query_language
    """

    # S-1: enterprise private-document search is a privileged INTERNAL operation.
    required_trust_level = TrustLevel.INTERNAL

    def execute(self, state: dict[str, Any]) -> dict[str, Any]:
        # Progress (non-terminal) event for the caller. Outside the Marketplace runtime
        # this resolves to a no-op emitter, so it is safe on every entry path.
        emitter().emit_event(
            event_type=EventType.PROGRESS_UPDATE,
            message="Checking the request...",
            metadata={"step": "pre_process"},
        )
        query = str(state.get("user_input") or state.get("user_query", ""))
        sanitized = sanitize_query(query)

        # S-2: block credential patterns in the raw query.
        if detect_credentials(sanitized):
            emit_trace_event("query_normalize_blocked", {"reason": "credential_in_query"}, state)
            return {
                "normalized_query": "",
                "query_language": "",
                "status": AgentStatus.ERROR,
                "error_log": ["SECURITY: Credential pattern detected in query"],
            }

        if len(sanitized.strip()) < _MIN_QUERY_LEN:
            return {
                "normalized_query": "",
                "query_language": "",
                "status": AgentStatus.ERROR,
                "error_log": ["Query too short"],
            }
        if len(sanitized) > _MAX_QUERY_LEN:
            sanitized = sanitized[:_MAX_QUERY_LEN]

        lang = self._detect_language(sanitized)
        normalized = re.sub(r"\s+", " ", sanitized).strip()

        emit_trace_event("query_normalized", {"language": lang}, state)
        return {
            "normalized_query": normalized,
            "query_language": lang,
            "status": AgentStatus.SUCCESS,
        }

    @staticmethod
    def _detect_language(text: str) -> str:
        """Simple heuristic: count CJK characters."""
        cjk = sum(1 for c in text if "　" <= c <= "鿿" or "＀" <= c <= "￯")
        ratio = cjk / max(len(text), 1)
        if ratio > 0.3:
            return "ja"
        if ratio > 0.05:
            return "mixed"
        return "en"

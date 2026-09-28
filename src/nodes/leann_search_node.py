"""CMN-C1-172 — LeannSearchNode (main slot).

Core retrieval capability: on-device LEANN vector search over the enterprise
corpus, followed by access control + APPI 2026 PII redaction. All processing
is on-device — no data leaves the local process.

Node contract: extend FunctionNode; override execute(self, state) -> dict (no
config param); return changed fields with an AgentStatus.* enum status. The S-1
trust gate is enforced by the framework from required_trust_level.
"""

from __future__ import annotations

import json
import time
from typing import Any

from framework.nodes.function_node import FunctionNode
from shared.services.events import emitter
from shared.services.events.types import EventType
from framework.schemas.agent_status import AgentStatus
from framework.schemas.trust_level import TrustLevel
from shared.utils.audit_logger import emit_trace_event

from src.services.leann_service import DEFAULT_CORPUS_PATH, LeannSearchService
from src.services.privacy_service import PrivacyFilterService
from src.services.security_service import detect_credentials


def _halted(state: dict[str, Any]) -> bool:
    return bool(state.get("error_log")) or state.get("status") == AgentStatus.ERROR.value


class LeannSearchNode(FunctionNode):
    """On-device LEANN search + access-control/PII filter.

    Input:  normalized_query, input_context.{corpus_path, user_id}
    Output: raw_results, search_elapsed_ms, filtered_results, filtered_count, pii_redacted
    """

    # S-1: corpus access is a privileged INTERNAL operation.
    required_trust_level = TrustLevel.INTERNAL

    def __init__(self, top_k: int = 10):
        self._search = LeannSearchService(top_k=top_k)
        self._privacy = PrivacyFilterService()

    def execute(self, state: dict[str, Any]) -> dict[str, Any]:
        # Progress (non-terminal) event for the caller. Outside the Marketplace runtime
        # this resolves to a no-op emitter, so it is safe on every entry path.
        emitter().emit_event(
            event_type=EventType.PROGRESS_UPDATE,
            message="Working on the request...",
            metadata={"step": "main"},
        )
        if _halted(state):
            return {}

        query = state.get("normalized_query", "")
        if not query:
            return {
                "raw_results": "[]",
                "search_elapsed_ms": 0,
                "filtered_results": "[]",
                "filtered_count": 0,
                "pii_redacted": False,
                "status": AgentStatus.ERROR,
                "error_log": ["Empty query — cannot search"],
            }

        input_context = state.get("input_context", {})
        corpus_path = state.get("corpus_path") or input_context.get("corpus_path") or DEFAULT_CORPUS_PATH
        user_id = state.get("user_id") or input_context.get("user_id", "")

        # ── On-device search ──────────────────────────────────────────────────
        t0 = time.monotonic()
        try:
            results = self._search.search(query, corpus_path)
        except ValueError as exc:
            # Network corpus path / data-minimization violation.
            return {
                "raw_results": "[]",
                "search_elapsed_ms": 0,
                "filtered_results": "[]",
                "filtered_count": 0,
                "pii_redacted": False,
                "status": AgentStatus.ERROR,
                "error_log": [str(exc)],
            }
        except FileNotFoundError:
            return {
                "raw_results": "[]",
                "search_elapsed_ms": 0,
                "filtered_results": "[]",
                "filtered_count": 0,
                "pii_redacted": False,
                "status": AgentStatus.ERROR,
                "error_log": [f"Corpus index not found: {corpus_path}"],
            }
        elapsed_ms = int((time.monotonic() - t0) * 1000)
        raw_results = json.dumps(results)

        # S-3 on retrieval output.
        if detect_credentials(raw_results):
            emit_trace_event("leann_search_blocked", {"reason": "credential_in_results"}, state)
            return {
                "raw_results": "[]",
                "search_elapsed_ms": elapsed_ms,
                "filtered_results": "[]",
                "filtered_count": 0,
                "pii_redacted": False,
                "status": AgentStatus.ERROR,
                "error_log": ["S3_BLOCKED: Credential detected in search results"],
            }

        # ── Access control + PII redaction ────────────────────────────────────
        cleaned, pii_redacted = self._privacy.filter_and_redact(results, user_id)
        filtered_results = json.dumps(cleaned)

        if detect_credentials(filtered_results):
            emit_trace_event("privacy_filter_blocked", {"reason": "credential_in_filtered"}, state)
            return {
                "raw_results": raw_results,
                "search_elapsed_ms": elapsed_ms,
                "filtered_results": "[]",
                "filtered_count": 0,
                "pii_redacted": False,
                "status": AgentStatus.ERROR,
                "error_log": ["S3_BLOCKED: Credential in filtered results"],
            }

        emit_trace_event(
            "leann_search_complete",
            {"elapsed_ms": elapsed_ms, "result_count": len(results), "filtered_count": len(cleaned)},
            state,
        )
        return {
            "raw_results": raw_results,
            "search_elapsed_ms": elapsed_ms,
            "filtered_results": filtered_results,
            "filtered_count": len(cleaned),
            "pii_redacted": pii_redacted,
            "status": AgentStatus.SUCCESS,
        }

"""CMN-C1-172 — ResponseFormatNode (post_process slot).

Formats ranked filtered results with source citations and the APPI 2026 advisory.

Node contract: extend FunctionNode; override execute(self, state) -> dict (no
config param); return changed fields with an AgentStatus.* enum status. The S-1
trust gate is enforced by the framework from required_trust_level.
"""

from __future__ import annotations

import json
from typing import Any

from framework.nodes.function_node import FunctionNode
from shared.services.events import emitter
from shared.services.events.types import EventType
from framework.schemas.agent_status import AgentStatus
from framework.schemas.trust_level import TrustLevel
from shared.utils.audit_logger import emit_trace_event

from src.services.security_service import apply_s3_gate

_ADVISORY = (
    "\n\n---\n"
    "※ 本検索結果は情報提供を目的としています。"
    "個人情報の取り扱いは社内APPIポリシーに従ってください。"
    " (APPI 2026 advisory)"
)

_NO_RESULTS_MSG = "検索結果が見つかりませんでした。クエリを変更して再度お試しください。"


def _halted(state: dict[str, Any]) -> bool:
    return bool(state.get("error_log")) or state.get("status") == AgentStatus.ERROR.value


class ResponseFormatNode(FunctionNode):
    """Render ranked filtered results into a Japanese markdown response.

    Input:  filtered_results, normalized_query, pii_redacted, search_elapsed_ms
    Output: response (markdown), result_count
    """

    # S-1: privileged INTERNAL operation (consistent with the rest of the pipeline).
    required_trust_level = TrustLevel.INTERNAL

    def execute(self, state: dict[str, Any]) -> dict[str, Any]:
        # Progress (non-terminal) event for the caller. Outside the Marketplace runtime
        # this resolves to a no-op emitter, so it is safe on every entry path.
        emitter().emit_event(
            event_type=EventType.PROGRESS_UPDATE,
            message="Preparing the result...",
            metadata={"step": "post_process"},
        )
        if _halted(state):
            emit_trace_event("response_format_skipped", {"reason": "upstream_error"}, state)
            return {"status": AgentStatus.ERROR}

        filtered_json = state.get("filtered_results", "[]")
        query = state.get("normalized_query", "")
        pii_redacted = state.get("pii_redacted", False)
        elapsed_ms = state.get("search_elapsed_ms", 0)

        try:
            results: list[dict[str, Any]] = json.loads(filtered_json)
        except (json.JSONDecodeError, TypeError):
            return {
                "response": "エラーが発生しました: 結果の解析に失敗しました",
                "result_count": 0,
                "status": AgentStatus.ERROR,
                "error_log": ["ResponseFormatNode: invalid filtered_results JSON"],
            }

        if not results:
            no_hit = _NO_RESULTS_MSG + _ADVISORY
            return {
                "response": no_hit,
                "formatted_output": no_hit,
                "result_count": 0,
                "status": AgentStatus.SUCCESS,
            }

        lines = [f"## 検索結果: {query}\n", f"*{len(results)}件 ({elapsed_ms}ms)*\n"]
        if pii_redacted:
            lines.append("*⚠️ 一部の個人情報はAPPI 2026に基づきマスクされました。*\n")

        for i, doc in enumerate(results, start=1):
            score = doc.get("score", 0.0)
            snippet = doc.get("snippet", "")
            path = doc.get("path", "")
            lines.append(f"### {i}. スコア: {score:.3f}\n" f"**ファイル:** `{path}`\n\n" f"{snippet}\n")

        response = "\n".join(lines) + _ADVISORY

        # S-3: credential check on rendered output.
        if apply_s3_gate(response) != response:
            emit_trace_event("response_format_blocked", {"reason": "credential_in_response"}, state)
            return {
                "response": "S3_BLOCKED: 出力にクレデンシャルが検出されました",
                "result_count": 0,
                "status": AgentStatus.ERROR,
                "error_log": ["S3_BLOCKED: Credential detected in response"],
            }

        emit_trace_event("response_formatted", {"result_count": len(results)}, state)
        return {
            "response": response,
            "formatted_output": response,
            "result_count": len(results),
            "status": AgentStatus.SUCCESS,
        }

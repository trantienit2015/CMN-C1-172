"""CMN-C1-172 — State schema.

State for the LEANN on-device enterprise document search pipeline.

Extends the framework ``AgentState`` (a flat TypedDict). All agent-specific
values are JSON-serializable primitives (str, int, bool, None, list[dict]).
No Pydantic models, dataclasses, credentials, or InvocationContext are stored
in State — it is persisted via LangGraph checkpoints (msgpack), so only
msgpack-safe primitives are permitted (ADR-005 / state-safety §3).

Trust level is NOT a State field: S-1 is enforced by the framework from each
node's ``required_trust_level`` class variable and the caller's
``InvocationContext`` (mirrored into ``caller_trust_level`` by the framework,
never declared here).
"""

from __future__ import annotations

from framework.schemas.agent_state import AgentState


class CMNPrivateDocSearchState(AgentState):
    """Agent state. Shared fields (user_input, status, session_id, node_history,
    error_log, …) are inherited from AgentState; only agent-specific fields below."""

    # ── Input (caller-provided via input_context) ─────────────────────────────
    user_query: str  # Raw query from the end user (also seeded as user_input)
    user_id: str  # User identifier for access control
    corpus_path: str  # Absolute path to the on-device LEANN index

    # ── pre_process (QueryNormalize) output ───────────────────────────────────
    normalized_query: str  # Cleaned, expanded query
    query_language: str  # Detected language: "ja" | "en" | "mixed"

    # ── main (LEANN search + privacy filter) output ───────────────────────────
    raw_results: str  # JSON-serialized list[dict]: [{doc_id, score, snippet, path}]
    search_elapsed_ms: int  # Search latency in milliseconds
    filtered_results: str  # JSON-serialized list[dict]: access-controlled subset
    filtered_count: int  # Number of results after filtering
    pii_redacted: bool  # True if any PII was redacted

    # ── post_process (ResponseFormat) output ──────────────────────────────────
    response: str  # Final formatted response (markdown)
    formatted_output: str  # type: ignore[misc]  # Mirror of response — surfaced as result["output"] by get_output()
    result_count: int  # Number of results returned to user

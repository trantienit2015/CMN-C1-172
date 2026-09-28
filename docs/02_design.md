# CMN-C1-172 — Design Specification

| Field | Value |
|-------|-------|
| Template ID | CMN-C1-172 |
| Pattern | RAGAgent (on-device document search) |
| Category | Cat 1 — CMN (Cross-Industry) |
| Inheritance | **L1 Base** — `AgentBaseGraph` (direct inheritance; no L2 base agent) |
| Level 2 type | RAGAgent *pattern* used as conceptual reference only — the graph inherits L1 `AgentBaseGraph` directly |
| Slots | 3 domain slots on the fixed backbone |
| Regime | AgentCore `src/` layout |

---

## 1. Architecture Overview

The graph class **is** the agent: `EnterprisePrivateDocSearchAgent(AgentBaseGraph)`.
It fills the fixed framework backbone's three domain slots; `initialize` and
`finalize` are injected by `super().register_nodes()`. The framework owns routing,
the S-1 trust gate, timing, error capture, and `node_history`.

```
START → initialize → pre_process → main → {route} → post_process → finalize → END
                      QueryNormalize  LeannSearch+         ResponseFormat
                                      PrivacyFilter
```

**Key property:** all processing happens on-device. No data is transmitted to
external services — APPI 2026 data-minimization compliant by architecture.

| Slot | Node | Responsibility |
|------|------|----------------|
| initialize | framework `InitializeNode` | backbone setup (injected) |
| pre_process | `QueryNormalizeNode` | normalize + language-detect + S-2 input credential gate |
| main | `LeannSearchNode` | on-device LEANN search + access control + APPI PII redaction + S-3 |
| post_process | `ResponseFormatNode` | render Japanese markdown + citations + APPI 2026 advisory + S-3 |
| finalize | framework `FinalizeNode` | backbone finalization (injected) |

Domain logic lives in services under `src/services/`:
- `leann_service.LeannSearchService` — LEANN adapter (synthetic in CI, `leann.search` in production).
- `privacy_service.PrivacyFilterService` — access control (`/restricted/` deny) + PII redaction.
- `security_service` — credential detection / `apply_s3_gate` / query sanitization (pure functions).

---

## 2. State Schema (`src/schemas/state.py`)

`CMNPrivateDocSearchState(AgentState)` — extends the framework flat `TypedDict`.
All agent-specific values are JSON-serializable primitives.

| Field | Type | Set by |
|-------|------|--------|
| `user_query` | `str` | Input (query is also seeded as `user_input`) |
| `user_id` | `str` | Input (via `input_context`) |
| `corpus_path` | `str` | Input (via `input_context`, optional) |
| `normalized_query` | `str` | pre_process |
| `query_language` | `str` | pre_process |
| `raw_results` | `str` (JSON) | main |
| `search_elapsed_ms` | `int` | main |
| `filtered_results` | `str` (JSON) | main |
| `filtered_count` | `int` | main |
| `pii_redacted` | `bool` | main |
| `response` | `str` | post_process |
| `formatted_output` | `str` | post_process (surfaced as `result["output"]`) |
| `result_count` | `int` | post_process |

**State safety:** no Pydantic models, no credentials, no `InvocationContext` stored.
Trust level is **not** a State field — S-1 is enforced by the framework from each
node's `required_trust_level` class variable and the caller's `InvocationContext`
(`caller_trust_level`), never declared in the schema.

---

## 3. Node Contract

Each node extends `FunctionNode` and overrides `execute(self, state) -> dict`
(no `config` parameter). Returns only changed fields and sets `status` to an
`AgentStatus.*` **enum**. Nodes never define `_invoke_impl()` and never override
`__call__()` — the framework owns invocation, routing, retry, and the S-1 gate.

### 3-1. QueryNormalizeNode (pre_process)
- Input: `user_input` (the raw query)
- Output: `normalized_query`, `query_language`
- Strips HTML, blocks credentials (S-2), validates length (2–512 chars), CJK-ratio language detection.

### 3-2. LeannSearchNode (main)
- Input: `normalized_query`, `input_context.{corpus_path, user_id}`
- Output: `raw_results`, `search_elapsed_ms`, `filtered_results`, `filtered_count`, `pii_redacted`
- Rejects network corpus paths (`http://`, `s3://`, …) — data minimization.
- LEANN search → access control (`/restricted/` non-admin deny, non-local source deny) → PII redaction.
- S-3 credential check on retrieved and filtered output.

### 3-3. ResponseFormatNode (post_process)
- Input: `filtered_results`, `normalized_query`, `pii_redacted`, `search_elapsed_ms`
- Output: `response`, `formatted_output`, `result_count`
- Japanese markdown with source path citations + relevance scores; APPI 2026 advisory always appended.
- S-3 gate via `apply_s3_gate()` before return.

---

## 4. Security Model (5-layer)

| Layer | Implementation |
|-------|---------------|
| S-1 | `required_trust_level: "INTERNAL"` in `config/agent.yaml`; each node declares `required_trust_level = TrustLevel.INTERNAL`. The framework `BaseNode.__call__` denies an under-trusted caller before `execute()`. |
| S-2 | JWT auth at the entry point; `caller_trust_level` carried on `InvocationContext`. Per-node credential detection on inputs. |
| S-3 | Secrets via the provider pattern at the entry point (`secrets_factory` + `bound_secrets` + `provision_secrets` in `src/api/server.py`) — never `os.environ`, never stored in state. Output credential gate via `apply_s3_gate()`. |
| S-4 | `emit_trace_event(event_type, payload, state)` from `shared.utils.audit_logger` in side-effect nodes. |
| S-5 | Framework import-time credential scan. |

Public entry: `Graph().compile()` then `agent.invoke(user_input, ctx=ctx, input_context=...)`
— never `.run()`.

---

## 5. LEANN Integration Design

```python
# Production (when the leann package is available), inside LeannSearchService.search():
import leann
index = leann.load_index(corpus_path)
results = index.search(query, top_k=self.top_k)   # each: {doc_id, score, snippet, path, source_type: "local"}
```

Adapter interface: `LeannSearchService.search()` encapsulates the LEANN API — when
the LEANN API changes, only this method needs updating. CI returns deterministic
synthetic results.

---

## 6. 電子帳簿保存法 2024 Corpus Notes

- Documents preserved under 電子帳簿保存法 are stored as local files.
- `corpus_path` points to the on-device LEANN index built from these files.
- No corpus data is transmitted to cloud — satisfies the data minimization principle.

---

## 7. Risks & Mitigations

| Risk | Mitigation |
|------|------------|
| LEANN API instability (pre-v1.0) | Adapter pattern in `LeannSearchService.search()` |
| Large corpus index build time | Async incremental indexing; documented max corpus size guidance |
| Access control misconfiguration | `is_allowed()` defaults-deny for `/restricted/`; unit tested |
| PII leak in snippets | `redact_pii()` with 4 pattern classes; unit + service tested |

---

*Migrated to the AgentCore `src/` regime — 2026-06-17.*

## 8. Deployment entry points

The agent is reachable through two entry points, and both resolve their runtime inputs the same way.

| Entry point | File | Used by |
|---|---|---|
| Standalone HTTP | `src/api/server.py` | staging rehearsal, direct invocation |
| Marketplace one-shot Pod | `cli.py` | the platform runner (container `CMD`) |

Both read runtime parameters from `config/config.yaml` — the manifest carries discovery metadata
only — and both scope secrets to the same location (`namespace=cmn`, `agent_name=cmn-c1-172`), so a
secret provisioned for one path resolves identically on the other.

**No LLM client is constructed at either entry point.** The pipeline is deterministic; a client
may still be injected through `config["llm"]` by a caller that has one.

**Progress events.** Each pipeline stage emits a non-terminal progress event at its start, so a
caller sees the run advancing. Outside the Marketplace runtime the emitter resolves to a no-op, so
the same code is safe on every path. Terminal events belong to the platform runner and are never
emitted by this agent.

**Caller authentication at the standalone entry point.** A caller that no upstream middleware
vouched for stays anonymous unless it presents a deployment-level credential: the external bearer
token grants the verified-external level, and a separate staging-only runner credential is the only
way to reach the internal level. Trust established upstream is never changed.

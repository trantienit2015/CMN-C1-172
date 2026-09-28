# CMN-C1-172 — Test Specification

| Field | Value |
|-------|-------|
| Template ID | CMN-C1-172 |
| Created | 2026-05-26 |

---

## 1. Unit Test Cases

### TC-001: QueryNormalizeNode — normal query
- Input: `{"user_query": "Osaka expansion Q3"}`
- Expected: `normalized_query` = "Osaka expansion Q3", `query_language` = "en", `error` = None

### TC-002: QueryNormalizeNode — Japanese query
- Input: `{"user_query": "大阪展開プランQ3"}`
- Expected: `query_language` = "ja"

### TC-003: QueryNormalizeNode — query too short
- Input: `{"user_query": "a"}`
- Expected: `error` = "Query too short", `normalized_query` = ""

### TC-004: QueryNormalizeNode — credential in query (S-2)
- Input: `{"user_query": "sk-" + "x"*25}`
- Expected: `error` contains "SECURITY" or "S2_BLOCKED"

### TC-005: LEANNSearchNode — normal search
- Input: `{"normalized_query": "delivery delays", "corpus_path": "/tmp/test"}`
- Expected: `raw_results` is valid JSON list, `search_elapsed_ms` >= 0

### TC-006: LEANNSearchNode — network corpus path rejected
- Input: `{"normalized_query": "test", "corpus_path": "https://evil.example.com/index"}`
- Expected: `error` contains "SECURITY"

### TC-007: LEANNSearchNode — empty query
- Input: `{"normalized_query": "", "corpus_path": "/tmp/test"}`
- Expected: `error` = "Empty query — cannot search"

### TC-008: PrivacyFilterNode — restricted path blocked for non-admin
- Input: raw_results with `/restricted/` path, `user_id` = "emp_001"
- Expected: that doc excluded from `filtered_results`

### TC-009: PrivacyFilterNode — restricted path allowed for admin
- Input: raw_results with `/restricted/` path, `user_id` = "admin_001"
- Expected: that doc included in `filtered_results`

### TC-010: PrivacyFilterNode — PII redaction (email)
- Input: snippet containing `user@example.com`
- Expected: snippet in output contains `[EMAIL]`, `pii_redacted` = True

### TC-011: ResponseFormatNode — no results
- Input: `{"filtered_results": "[]", "normalized_query": "test"}`
- Expected: `response` contains "見つかりませんでした", `result_count` = 0

### TC-012: ResponseFormatNode — APPI advisory always present
- Input: any valid filtered_results
- Expected: `response` contains "APPI 2026 advisory"

### TC-013: ResponseFormatNode — S3 credential blocked
- Input: filtered_results with `"sk-" + "x"*30` in snippet
- Expected: `response` = "S3_BLOCKED: ..."

---

## 2. Integration Test

### IT-001: End-to-end pipeline (happy path)
- Input: `{"user_query": "Osaka expansion", "user_id": "emp_001", "corpus_path": "/tmp/test_idx"}`
- Expected: `response` is non-empty markdown, `result_count` >= 0, `error` = None
- All state values are str/int/bool/None (PB-2 equivalent)

### IT-002: Error propagation
- Input: `{"user_query": "a"}` (too short)
- Expected: `error` set after QueryNormalize, subsequent nodes pass through error without crashing

---

## 3. Proof-of-Boundary (PB) Items

| PB ID | Boundary | Test |
|-------|----------|------|
| PB-1 | `_emit_trace_event()` fires without error | test_pb1_emit_trace_event |
| PB-2 | All state values are primitives after pipeline | test_pb2_state_primitives |
| PB-3 | S3 gate blocks credential in response | test_pb3_s3_credential_blocked |
| PB-4 | PII redacted in filtered results | test_pb4_pii_redacted |
| PB-5 | Network corpus path rejected | test_pb5_network_corpus_rejected |
| PB-6 | Non-admin cannot see restricted docs | test_pb6_access_control_boundary |

---

*Auto-generated — 2026-05-26*

## 4. Deployment path tests

### TC-DEP-01 Marketplace entry point identity — `tests/unit/test_cli_entry_point.py`

| Case | Expected |
|---|---|
| Identity is concrete | `agent_name` / `namespace` are non-empty and not the runner default |
| Identity matches the HTTP entry point | the values equal what `src/api/server.py` passes to `secrets_factory`; where that entry point provisions no secrets, they equal the manifest `namespace` and the lower-cased template id |
| The runner call uses the constants | `run_agent_marketplace` is called with the module constants, not inline literals |

### TC-DEP-02 Standalone entry point boundary — `tests/proof_of_boundary/test_server_llm_injection.py`

| Case | Expected |
|---|---|
| Boots with no credential provisioned | the module imports and the app/agent objects are constructed |
| External bearer never reaches the internal level | resolves to the verified-external level |
| Staging runner credential reaches the internal level | resolves to the internal level |
| Wrong or missing bearer while auth is enabled | rejected with 401 |

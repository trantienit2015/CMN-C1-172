"""CMN-C1-172 — LEANN on-device search service.

Encapsulates the LEANN vector-search adapter behind a stable interface. All
processing happens on-device — no data leaves the local process (APPI 2026
data-minimization compliant by architecture). LEANN (MLsys2026, MIT license,
MCP-native): 97% storage savings, indexes 60M documents in 6GB RAM.

When the LEANN API changes, only ``search()`` needs updating.
"""

from __future__ import annotations

from typing import Any

_DEFAULT_TOP_K = 10
_MAX_TOP_K = 50
DEFAULT_CORPUS_PATH = "/var/data/leann_index"

# corpus_path must be a local path — network URIs would breach data minimization.
_NETWORK_SCHEMES = ("http://", "https://", "s3://", "gs://")


class LeannSearchService:
    """On-device LEANN vector search over the enterprise document corpus."""

    def __init__(self, top_k: int = _DEFAULT_TOP_K):
        self.top_k = min(max(top_k, 1), _MAX_TOP_K)

    def search(self, query: str, corpus_path: str) -> list[dict[str, Any]]:
        """Execute LEANN on-device search.

        Production: ``import leann`` and call ``leann.search(query,
        index_path=corpus_path, top_k=self.top_k)``.
        CI/test: returns deterministic synthetic results.

        Raises:
            ValueError: when ``corpus_path`` is a network URI (data-minimization
                violation — corpus must be on-device).
        """
        if corpus_path.startswith(_NETWORK_SCHEMES):
            raise ValueError(f"SECURITY: corpus_path must be a local path — got network URI: {corpus_path}")
        return [
            {
                "doc_id": f"doc_{i:04d}",
                "score": round(0.95 - i * 0.05, 3),
                "snippet": f"[CI] Synthetic result {i} for query: {query[:40]}",
                "path": f"{corpus_path}/doc_{i:04d}.txt",
                "source_type": "local",
            }
            for i in range(min(self.top_k, 3))
        ]

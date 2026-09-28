"""CMN-C1-172 — Security helper service.

Self-contained credential/PII detection and output-gate helpers used by the
search pipeline. Pure functions, no framework imports, no side effects.

These helpers police credential leakage in queries and rendered output. They
complement (but do not replace) the framework's 5-layer security model: the S-1
trust gate is enforced by the framework before each node's ``execute()`` (via the
node's ``required_trust_level`` class variable), and S-5 credential scanning runs
at import time. This service provides the domain-level content checks the search
nodes apply on their inputs and outputs.
"""

from __future__ import annotations

import re

# Credential patterns blocked on query input and rendered output.
CREDENTIAL_PATTERNS = [
    r"sk-[a-zA-Z0-9]{20,}",
    r"eyJ[a-zA-Z0-9._-]{10,}",
    r"AKIA[A-Z0-9]{16}",
    r"Bearer\s+[a-zA-Z0-9._-]{20,}",
    r"(?i)(api[_-]?key|secret|password|token)\s*=\s*[\"'][^\"']{8,}[\"']",
]


def sanitize_query(query: str, strip_html: bool = True) -> str:
    """Strip HTML tags from a raw query string (defensive input cleaning)."""
    if strip_html:
        query = re.sub(r"<[^>]+>", "", query)
    return query


def detect_credentials(text: str) -> list[str]:
    """Return the list of credential patterns that match ``text`` (empty if none)."""
    return [pat for pat in CREDENTIAL_PATTERNS if re.search(pat, text)]


def apply_s3_gate(output: str) -> str:
    """S-3 output gate: replace the output with a block message if it contains credentials."""
    if detect_credentials(output):
        return "BLOCKER: Credential detected in output"
    return output

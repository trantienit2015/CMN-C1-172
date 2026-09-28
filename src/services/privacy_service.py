"""CMN-C1-172 — Privacy & access-control service.

APPI 2026 data-minimization: access control (remove documents the requesting
user is not permitted to see) and PII redaction in document snippets. Pure
logic, no framework imports, no side effects.
"""

from __future__ import annotations

import re
from typing import Any

# PII redaction patterns applied to document snippets.
_PII_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}"), "[EMAIL]"),
    (re.compile(r"\b\d{3}-\d{4}-\d{4}\b"), "[PHONE]"),
    (re.compile(r"\b\d{4}-\d{4}-\d{4}\b"), "[MYNUMBER]"),
    (re.compile(r"\b\d{4}[-\s]?\d{4}[-\s]?\d{4}[-\s]?\d{4}\b"), "[CARD]"),
]


class PrivacyFilterService:
    """Access control + APPI 2026 PII redaction over search results."""

    def filter_and_redact(self, results: list[dict[str, Any]], user_id: str) -> tuple[list[dict[str, Any]], bool]:
        """Return (cleaned_results, pii_redacted) after access control + PII redaction."""
        allowed = [r for r in results if self.is_allowed(r, user_id)]
        redacted_any = False
        cleaned: list[dict[str, Any]] = []
        for doc in allowed:
            doc_out, redacted = self.redact_pii(doc)
            cleaned.append(doc_out)
            if redacted:
                redacted_any = True
        return cleaned, redacted_any

    @staticmethod
    def is_allowed(doc: dict[str, Any], user_id: str) -> bool:
        """Access control check. Production: call ACL service. Defaults-deny for /restricted/."""
        path = doc.get("path", "")
        if "/restricted/" in path and not user_id.startswith("admin_"):
            return False
        source_type = doc.get("source_type", "local")
        if source_type != "local":
            return False
        return True

    @staticmethod
    def redact_pii(doc: dict[str, Any]) -> tuple[dict[str, Any], bool]:
        """Redact PII patterns in the snippet field. Returns (doc, redacted)."""
        snippet = doc.get("snippet", "")
        redacted = False
        for pattern, replacement in _PII_PATTERNS:
            new_snippet, n = pattern.subn(replacement, snippet)
            if n:
                snippet = new_snippet
                redacted = True
        if redacted:
            doc = {**doc, "snippet": snippet}
        return doc, redacted

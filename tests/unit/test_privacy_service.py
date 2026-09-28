"""CMN-C1-172 — PrivacyFilterService unit tests (access control + PII redaction)."""
from __future__ import annotations

from src.services.privacy_service import PrivacyFilterService


class TestPrivacyFilterService:
    def setup_method(self):
        self.svc = PrivacyFilterService()

    def test_pii_email_redacted(self):
        docs = [{
            "doc_id": "doc1", "score": 0.9,
            "snippet": "Contact user@example.co.jp for approval",
            "path": "/var/data/doc1.txt", "source_type": "local",
        }]
        cleaned, redacted = self.svc.filter_and_redact(docs, "emp_001")
        assert redacted is True
        assert "example.co.jp" not in cleaned[0]["snippet"]
        assert "[EMAIL]" in cleaned[0]["snippet"]

    def test_restricted_doc_blocked_for_non_admin(self):
        docs = [
            {"doc_id": "restricted", "score": 0.9, "snippet": "secret",
             "path": "/var/data/restricted/m.txt", "source_type": "local"},
            {"doc_id": "public", "score": 0.7, "snippet": "ok",
             "path": "/var/data/public/p.txt", "source_type": "local"},
        ]
        cleaned, _ = self.svc.filter_and_redact(docs, "emp_001")
        ids = [d["doc_id"] for d in cleaned]
        assert "restricted" not in ids
        assert "public" in ids

    def test_restricted_doc_allowed_for_admin(self):
        docs = [{"doc_id": "restricted", "score": 0.9, "snippet": "secret",
                 "path": "/var/data/restricted/m.txt", "source_type": "local"}]
        cleaned, _ = self.svc.filter_and_redact(docs, "admin_001")
        assert [d["doc_id"] for d in cleaned] == ["restricted"]

    def test_non_local_source_blocked(self):
        docs = [{"doc_id": "remote", "score": 0.9, "snippet": "x",
                 "path": "/var/data/doc.txt", "source_type": "cloud"}]
        cleaned, _ = self.svc.filter_and_redact(docs, "emp_001")
        assert cleaned == []

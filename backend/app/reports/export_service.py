import csv
import hashlib
import io
import json
import logging
from typing import Any, Dict, List, Optional, Tuple

from backend.app.reports.pdf_generator import pdf_generator
from backend.app.schemas.report import ForensicReportDocument

logger = logging.getLogger(__name__)


class ForensicExportService:
    """
    Forensic Report Export & Integrity Verification Service.
    Produces cryptographic SHA-256 checksums and serializes reports into JSON, PDF, and CSV formats.
    """

    @staticmethod
    def compute_sha256(data: bytes | str) -> str:
        """Compute cryptographic SHA-256 digest over string or bytes."""
        if isinstance(data, str):
            data = data.encode("utf-8")
        return hashlib.sha256(data).hexdigest()

    def export_as_json(self, doc: ForensicReportDocument) -> Tuple[str, str]:
        """
        Serialize report into formatted JSON and compute SHA-256 checksum.
        """
        doc_dict = doc.model_dump(mode="json")
        # Ensure report_hash is temporarily removed for deterministic content hashing
        doc_dict_for_hash = dict(doc_dict)
        doc_dict_for_hash["report_hash"] = None
        serialized_for_hash = json.dumps(doc_dict_for_hash, sort_keys=True, indent=2)
        content_hash = self.compute_sha256(serialized_for_hash)

        # Store computed hash in document
        doc_dict["report_hash"] = content_hash
        final_json = json.dumps(doc_dict, indent=2)
        return final_json, content_hash

    def export_as_pdf(self, doc: ForensicReportDocument) -> Tuple[bytes, str]:
        """
        Generate court-ready PDF document and compute SHA-256 checksum.
        """
        # First compute document content hash
        _, content_hash = self.export_as_json(doc)
        doc.report_hash = content_hash

        pdf_bytes = pdf_generator.generate_pdf_bytes(doc)
        pdf_hash = self.compute_sha256(pdf_bytes)
        return pdf_bytes, pdf_hash

    def export_timeline_as_csv(self, doc: ForensicReportDocument) -> str:
        """Export timeline section as standard CSV."""
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(["Timestamp", "EventType", "Application", "Actor", "Target", "ContentSummary", "CitationRef"])

        for entry in doc.timeline_section or []:
            writer.writerow([
                entry.timestamp,
                entry.event_type,
                entry.application or "",
                entry.actor or "",
                entry.target or "",
                entry.content_summary or "",
                entry.citation_ref,
            ])

        return output.getvalue()


export_service = ForensicExportService()

import logging
from typing import Any, Dict, List, Optional, Tuple
import uuid
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.models.canonical_evidence import CanonicalEvidence
from backend.app.models.evidence import Evidence
from backend.app.schemas.report import EvidenceCitation

logger = logging.getLogger(__name__)


class ForensicCitationEngine:
    """
    Evidence Citation & Verification Engine.
    Constructs, indexes, and strictly verifies forensic citations ensuring that every
    reported finding is traceable to verified case artifacts and original evidence files.
    """

    @staticmethod
    def create_citation(
        evidence_id: UUID,
        evidence_number: str,
        summary: str,
        artifact_id: Optional[UUID] = None,
        record_identifier: Optional[str] = None,
        source_file: Optional[str] = None,
        timestamp: Optional[str] = None,
        citation_index: int = 1,
    ) -> EvidenceCitation:
        """Construct a standardized citation reference."""
        citation_id = f"CIT-{citation_index:03d}"
        return EvidenceCitation(
            citation_id=citation_id,
            evidence_id=evidence_id,
            evidence_number=evidence_number,
            artifact_id=artifact_id,
            record_identifier=record_identifier,
            source_file=source_file,
            timestamp=timestamp,
            summary=summary,
        )

    @staticmethod
    async def validate_citations(
        citations: List[EvidenceCitation],
        case_id: UUID,
        session: AsyncSession,
    ) -> Tuple[bool, List[str]]:
        """
        Validate all citation references against active case database records.
        Ensures strict case ownership, checks for broken references, and prevents hallucinated IDs.
        """
        errors: List[str] = []
        if not citations:
            return True, []

        # 1. Fetch valid evidence IDs for case
        ev_query = select(Evidence.id).where(Evidence.case_id == case_id)
        ev_res = await session.execute(ev_query)
        valid_evidence_ids = set(ev_res.scalars().all())

        # 2. Fetch valid canonical artifact IDs for case
        art_ids_to_check = [c.artifact_id for c in citations if c.artifact_id]
        valid_artifact_ids = set()
        if art_ids_to_check:
            art_query = select(CanonicalEvidence.id).where(
                CanonicalEvidence.case_id == case_id,
                CanonicalEvidence.id.in_(art_ids_to_check),
            )
            art_res = await session.execute(art_query)
            valid_artifact_ids = set(art_res.scalars().all())

        # 3. Check each citation
        for c in citations:
            if c.evidence_id not in valid_evidence_ids:
                errors.append(
                    f"Citation '{c.citation_id}' references Evidence ID '{c.evidence_id}' "
                    f"which does not exist in Case '{case_id}'."
                )

            if c.artifact_id and c.artifact_id not in valid_artifact_ids:
                errors.append(
                    f"Citation '{c.citation_id}' references Artifact ID '{c.artifact_id}' "
                    f"which was not found in Case '{case_id}'."
                )

        is_valid = len(errors) == 0
        return is_valid, errors


citation_engine = ForensicCitationEngine()

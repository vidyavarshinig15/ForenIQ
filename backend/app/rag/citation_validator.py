import logging
import re
from typing import Dict, List, Tuple

from backend.app.schemas.rag import EvidenceCitation, EvidenceContextItem, RAGValidationReport

logger = logging.getLogger(__name__)


class CitationValidationService:
    """
    Validates evidence citations extracted from LLM responses.
    Prevents hallucinated citation IDs, cross-case references, and unsupported claims.
    """

    CITATION_REGEX = re.compile(r"\[?(EVIDENCE-\d{3,4})\]?", re.IGNORECASE)
    ALT_CITATION_REGEX = re.compile(r"\[?Evidence\s+(?:E)?(\d+)\]?", re.IGNORECASE)

    # Forensic safety prohibited terms
    PROHIBITED_INTENT_TERMS = [
        "guilty beyond doubt",
        "guilt is established",
        "criminal intent proven",
        "perpetrator confirmed guilty",
        "obviously committed the crime",
    ]

    def validate_citations(
        self,
        raw_answer: str,
        tag_lookup: Dict[str, EvidenceContextItem],
        active_case_id: str,
    ) -> Tuple[List[EvidenceCitation], RAGValidationReport, str]:
        """
        Extracts citations, validates existence against tag_lookup, checks case isolation,
        and produces structured citations plus validation report.
        """
        active_case_id_str = str(active_case_id).strip()
        found_tags: List[str] = []

        # Find primary tags e.g. [EVIDENCE-001]
        for match in self.CITATION_REGEX.finditer(raw_answer):
            tag = match.group(1).upper()
            if tag not in found_tags:
                found_tags.append(tag)

        # Find alternative tags e.g. Evidence 1 -> EVIDENCE-001
        for match in self.ALT_CITATION_REGEX.finditer(raw_answer):
            num = int(match.group(1))
            formatted = f"EVIDENCE-{num:03d}"
            if formatted not in found_tags:
                found_tags.append(formatted)

        valid_citations: List[EvidenceCitation] = []
        valid_tag_names: List[str] = []
        invalid_tag_names: List[str] = []
        cross_case_violations: List[str] = []
        unsupported_claims: List[str] = []

        # Check each found tag
        for tag in found_tags:
            if tag in tag_lookup:
                item = tag_lookup[tag]
                # Check case isolation
                if str(item.case_id).strip() != active_case_id_str:
                    cross_case_violations.append(tag)
                    logger.critical(
                        f"CRITICAL: Cross-case citation leak detected for tag {tag}. "
                        f"Item Case: {item.case_id}, Query Case: {active_case_id_str}"
                    )
                    continue

                valid_tag_names.append(tag)
                snippet = item.content[:150] + "..." if len(item.content) > 150 else item.content

                citation = EvidenceCitation(
                    citation_tag=tag,
                    evidence_id=item.evidence_id,
                    canonical_id=item.canonical_id,
                    artifact_type=item.artifact_type,
                    source_application=item.source_application,
                    timestamp=item.timestamp,
                    sender=item.sender,
                    receiver=item.receiver,
                    reason=f"Direct forensic record supporting statement ({item.artifact_type})",
                    content_snippet=snippet,
                    is_verified=True,
                )
                valid_citations.append(citation)
            else:
                invalid_tag_names.append(tag)
                logger.warning(f"Hallucinated or nonexistent citation tag detected: {tag}")

        # Check for prohibited intent / guilt declarations (ignoring quoted evidence content)
        unquoted_answer = re.sub(r'"[^"]*"', '', raw_answer).lower()
        for term in self.PROHIBITED_INTENT_TERMS:
            if term in unquoted_answer:
                unsupported_claims.append(f"Forensic safety violation: model generated prohibited claim '{term}'")

        # Determine overall validity
        is_valid = len(invalid_tag_names) == 0 and len(cross_case_violations) == 0 and len(unsupported_claims) == 0

        notes = []
        if valid_tag_names:
            notes.append(f"Successfully verified {len(valid_tag_names)} citation(s): {', '.join(valid_tag_names)}.")
        if invalid_tag_names:
            notes.append(f"Rejected {len(invalid_tag_names)} invalid citation tag(s): {', '.join(invalid_tag_names)}.")
        if cross_case_violations:
            notes.append(f"Blocked {len(cross_case_violations)} cross-case citation leak(s).")
        if unsupported_claims:
            notes.append(f"Flagged {len(unsupported_claims)} unsupported or prohibited claim(s).")

        validation_report = RAGValidationReport(
            is_valid=is_valid,
            total_citations_found=len(found_tags),
            valid_citations=valid_tag_names,
            invalid_citations=invalid_tag_names,
            cross_case_violations=cross_case_violations,
            unsupported_claims=unsupported_claims,
            validation_notes=" ".join(notes) or "Validation passed without warnings.",
        )

        # Sanitize answer if invalid citations were detected
        sanitized_answer = raw_answer
        for invalid_tag in invalid_tag_names:
            sanitized_answer = re.sub(
                rf"\[?{re.escape(invalid_tag)}\]?",
                f"[INVALID-UNSUPPORTED-REF: {invalid_tag}]",
                sanitized_answer,
            )

        return valid_citations, validation_report, sanitized_answer

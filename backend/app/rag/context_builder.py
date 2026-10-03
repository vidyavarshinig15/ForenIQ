import hashlib
import logging
from typing import Any, Dict, List, Optional, Tuple

from backend.app.core.config import settings
from backend.app.schemas.rag import ConflictingRecord, EvidenceContextItem

logger = logging.getLogger(__name__)


class EvidenceContextBuilder:
    """
    Constructs bounded, deduplicated, case-isolated forensic evidence context blocks
    for consumption by LLM providers in the RAG pipeline.
    """

    def __init__(
        self,
        max_context_records: Optional[int] = None,
        max_context_tokens: Optional[int] = None,
    ):
        self.max_context_records = max_context_records or settings.RAG_MAX_CONTEXT_RECORDS
        self.max_context_tokens = max_context_tokens or settings.RAG_MAX_CONTEXT_TOKENS

    @staticmethod
    def _estimate_tokens(text: str) -> int:
        """Rough token estimation (1 token ~= 4 characters for English forensic text)."""
        return max(1, len(text) // 4)

    @staticmethod
    def _compute_hash(content: str) -> str:
        return hashlib.sha256(content.strip().encode("utf-8")).hexdigest()

    def build_context(
        self,
        raw_search_results: List[Dict[str, Any]],
        case_id: str,
    ) -> Tuple[List[EvidenceContextItem], str, Dict[str, EvidenceContextItem], List[ConflictingRecord]]:
        """
        Processes raw retrieval results into:
        1. List of validated EvidenceContextItem
        2. Formatted prompt context string
        3. Lookup dictionary keyed by tag (e.g., 'EVIDENCE-001')
        4. List of detected conflicting evidence records
        """
        case_id_str = str(case_id).strip()
        filtered_items: List[EvidenceContextItem] = []
        seen_identifiers = set()
        seen_content_hashes = set()

        # Step 1: Case Isolation & Deduplication
        for idx, item in enumerate(raw_search_results):
            # Check case isolation
            item_case_id = str(item.get("case_id") or "").strip()
            if item_case_id and item_case_id != case_id_str:
                logger.warning(
                    f"SECURITY ALERT: Filtered cross-case evidence in RAG context builder. "
                    f"Target Case: {case_id_str}, Found Record Case: {item_case_id}"
                )
                continue

            canonical_id = str(item.get("canonical_id") or item.get("id") or f"gen-{idx}")
            evidence_id = str(item.get("evidence_id") or item.get("evidence_upload_id") or canonical_id)
            raw_artifact_id = str(item.get("raw_artifact_id") or "") if item.get("raw_artifact_id") else None
            artifact_type = str(item.get("artifact_type") or item.get("canonical_type") or "artifact").lower()
            source_app = item.get("source_application") or item.get("application") or item.get("source_app")
            
            # Extract timestamp
            timestamp = item.get("event_timestamp") or item.get("timestamp") or item.get("datetime")
            if timestamp and hasattr(timestamp, "isoformat"):
                timestamp = timestamp.isoformat()
            elif timestamp:
                timestamp = str(timestamp)

            sender = item.get("sender") or item.get("from_party") or item.get("sender_id") or item.get("caller")
            receiver = item.get("receiver") or item.get("to_party") or item.get("recipient") or item.get("callee")
            
            # Extract content text
            content = str(
                item.get("content")
                or item.get("message_text")
                or item.get("text_content")
                or item.get("snippet")
                or item.get("name")
                or item.get("description")
                or ""
            ).strip()

            if not content:
                # If no content, synthesize descriptive summary from metadata
                content = f"Record of type {artifact_type} ({source_app or 'Unknown App'}) at {timestamp or 'unknown time'}."

            content_hash = self._compute_hash(f"{artifact_type}|{sender}|{receiver}|{content}")
            unique_key = f"{canonical_id}:{content_hash}"

            # Deduplication: do not re-add exact duplicate records
            if unique_key in seen_identifiers or (content_hash in seen_content_hashes and len(content) > 30):
                continue

            seen_identifiers.add(unique_key)
            seen_content_hashes.add(content_hash)

            tag_index = len(filtered_items) + 1
            evidence_tag = f"EVIDENCE-{tag_index:03d}"

            context_item = EvidenceContextItem(
                evidence_tag=evidence_tag,
                evidence_id=evidence_id,
                canonical_id=canonical_id,
                raw_artifact_id=raw_artifact_id,
                case_id=case_id_str,
                artifact_type=artifact_type,
                source_application=str(source_app) if source_app else None,
                timestamp=str(timestamp) if timestamp else None,
                sender=str(sender) if sender else None,
                receiver=str(receiver) if receiver else None,
                content=content,
                source_file=str(item.get("source_file")) if item.get("source_file") else None,
                record_identifier=str(item.get("record_identifier") or item.get("original_id") or "") or None,
                relevance_score=float(item.get("score") or item.get("relevance_score") or 1.0),
                metadata={k: v for k, v in item.items() if k not in ("embedding", "content_vector")},
            )
            filtered_items.append(context_item)

            if len(filtered_items) >= self.max_context_records:
                break

        # Step 2: Token Budgeting & Formatted String Building
        formatted_blocks: List[str] = []
        tag_lookup: Dict[str, EvidenceContextItem] = {}
        total_tokens = 0
        final_items: List[EvidenceContextItem] = []

        for item in filtered_items:
            block = (
                f"[{item.evidence_tag}]\n"
                f"Artifact Type: {item.artifact_type}\n"
                f"Application: {item.source_application or 'N/A'}\n"
                f"Timestamp: {item.timestamp or 'N/A'}\n"
                f"Sender: {item.sender or 'N/A'}\n"
                f"Receiver: {item.receiver or 'N/A'}\n"
                f"Source File: {item.source_file or 'N/A'}\n"
                f"Record ID: {item.record_identifier or 'N/A'}\n"
                f"Evidence ID: {item.evidence_id}\n"
                f"Canonical ID: {item.canonical_id}\n"
                f"Content: {item.content}\n"
            )
            block_tokens = self._estimate_tokens(block)
            if total_tokens + block_tokens > self.max_context_tokens and final_items:
                logger.info(
                    f"RAG context token budget reached ({total_tokens} tokens). "
                    f"Trimming at {len(final_items)} records."
                )
                break

            total_tokens += block_tokens
            formatted_blocks.append(block)
            tag_lookup[item.evidence_tag] = item
            final_items.append(item)

        context_text = "\n".join(formatted_blocks)

        # Step 3: Conflict Detection (e.g. matching participants or event topics with different timestamps)
        conflicts = self._detect_conflicts(final_items)

        return final_items, context_text, tag_lookup, conflicts

    def _detect_conflicts(self, items: List[EvidenceContextItem]) -> List[ConflictingRecord]:
        """
        Scans retrieved evidence items for observable discrepancies (e.g. different timestamps
        or conflicting sender/receiver statements).
        """
        conflicts: List[ConflictingRecord] = []
        
        # Group by record_identifier if present
        grouped_by_rec_id: Dict[str, List[EvidenceContextItem]] = {}
        for it in items:
            if it.record_identifier:
                grouped_by_rec_id.setdefault(it.record_identifier, []).append(it)

        for rec_id, group in grouped_by_rec_id.items():
            if len(group) > 1:
                timestamps = {g.timestamp for g in group if g.timestamp}
                if len(timestamps) > 1:
                    conflicts.append(
                        ConflictingRecord(
                            field_name="timestamp",
                            records=[g.model_dump() for g in group],
                            conflict_description=(
                                f"Record '{rec_id}' appears with multiple conflicting timestamps: {list(timestamps)}"
                            ),
                        )
                    )

        return conflicts

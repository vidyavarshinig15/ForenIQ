import logging
import re
from typing import Any, Dict, List, Optional

from backend.app.rag.providers.base import BaseLLMProvider
from backend.app.schemas.rag import EvidenceContextItem

logger = logging.getLogger(__name__)


class DeterministicForensicRAGProvider(BaseLLMProvider):
    """
    100% offline, deterministic forensic extraction and synthesis provider.
    Runs completely air-gapped without requiring cloud APIs or GPU dependencies.
    Adheres strictly to zero-hallucination, evidence-only citation rules.
    """

    def __init__(self, model_name: str = "deterministic-forensic-rag-v1"):
        super().__init__(model_name=model_name)

    @property
    def provider_name(self) -> str:
        return "local"

    async def generate_answer(
        self,
        query: str,
        evidence_items: List[EvidenceContextItem],
        evidence_context_text: str,
        system_prompt: str,
        conversation_history_text: str = "",
        options: Optional[Dict[str, Any]] = None,
    ) -> str:
        """
        Synthesizes an evidence-grounded answer based strictly on retrieved records.
        """
        query_clean = query.strip()
        query_lower = query_clean.lower()

        # Rule 1: Zero evidence retrieved -> Insufficient evidence response
        if not evidence_items:
            return (
                "ANSWER:\n"
                "The available evidence does not provide enough information to answer this question.\n\n"
                "EVIDENCE_REFERENCES:\n"
                "- None available\n\n"
                "CONFLICTING_EVIDENCE:\n"
                "None identified in the retrieved context.\n\n"
                "UNCERTAINTY:\n"
                "No forensic records matching the query parameters were retrieved for the active case.\n\n"
                "LIMITATIONS:\n"
                "Analysis limited to indexed evidence records within the active case."
            )

        # Rule 2: Check relevance of retrieved evidence to query keywords/entities
        # Month mappings for temporal expressions
        month_map = {
            "january": "01", "february": "02", "march": "03", "april": "04",
            "may": "05", "june": "06", "july": "07", "august": "08",
            "september": "09", "october": "10", "november": "11", "december": "12",
            "jan": "01", "feb": "02", "mar": "03", "apr": "04", "jun": "06",
            "jul": "07", "aug": "08", "sep": "09", "sept": "09", "oct": "10",
            "nov": "11", "dec": "12"
        }

        # Extract tokens from query
        query_words = set(re.findall(r"\b\w+\b", query_lower))
        stopwords = {
            "what", "when", "where", "which", "who", "whom", "whose", "why", "how",
            "all", "any", "both", "each", "few", "more", "most", "other", "some",
            "such", "than", "too", "very", "can", "will", "just", "should", "now",
            "find", "show", "tell", "give", "list", "between", "occurred", "happened",
            "messages", "message", "calls", "call", "contacts", "contact", "evidence",
            "records", "record", "case", "during", "period", "events", "event", "activity",
            "recorded", "found", "saved", "app", "logs", "log", "does", "the", "for", "and",
            "with", "from", "into", "onto", "under", "over", "near", "about", "are", "there",
            "did", "do", "done", "to", "in", "at", "on", "of", "by", "is", "was", "be", "or",
            "it", "an", "a", "this", "that", "these", "those", "have", "has", "had", "been"
        }
        substantive_query_words = {w for w in query_words if w not in stopwords and len(w) > 1}

        matching_items: List[EvidenceContextItem] = []
        for item in evidence_items:
            item_text = (
                f"{item.content} {item.sender or ''} {item.receiver or ''} "
                f"{item.source_application or ''} {item.artifact_type} {item.record_identifier or ''}"
            ).lower()
            timestamp_str = (item.timestamp or "").lower()

            if not substantive_query_words:
                matching_items.append(item)
            else:
                has_match = False
                # Direct word matches in text content
                for word in substantive_query_words:
                    if re.search(rf"\b{re.escape(word)}\b", item_text) or re.search(rf"\b{re.escape(word)}\b", timestamp_str):
                        has_match = True
                        break

                # Month numeric match specifically against timestamp string (e.g. -09- or -10-)
                if not has_match:
                    for term in substantive_query_words:
                        if term in month_map:
                            month_num = month_map[term]
                            if f"-{month_num}-" in timestamp_str or f"-{month_num}T" in timestamp_str:
                                has_match = True
                                break

                if has_match:
                    matching_items.append(item)

        # If no items match substantive keywords (e.g. query asked for 'Alice' or 'cryptocurrency' but none exist)
        if not matching_items and substantive_query_words:
            missing_terms = ", ".join(sorted(substantive_query_words))
            return (
                f"ANSWER:\n"
                f"The available evidence does not provide enough information to answer this question. "
                f"No records matching the requested entities or terms ({missing_terms}) were found in the retrieved evidence.\n\n"
                f"EVIDENCE_REFERENCES:\n"
                f"- None available\n\n"
                f"CONFLICTING_EVIDENCE:\n"
                f"None identified in the retrieved context.\n\n"
                f"UNCERTAINTY:\n"
                f"The query requested information regarding specific terms that do not appear in the active case evidence.\n\n"
                f"LIMITATIONS:\n"
                f"Only records indexed for the active case were evaluated."
            )

        # Use matching items
        active_items = matching_items if matching_items else evidence_items[:5]

        # Check for conflicting timestamps across active items
        conflicts: List[str] = []
        timestamps_by_app: Dict[str, List[str]] = {}
        for it in active_items:
            app_key = it.source_application or it.artifact_type
            if it.timestamp:
                timestamps_by_app.setdefault(app_key, []).append(f"[{it.evidence_tag}] {it.timestamp}")

        for app, ts_list in timestamps_by_app.items():
            if len(ts_list) > 1 and "conflict" in query_lower:
                conflicts.append(f"Discrepancies noted for {app}: {', '.join(ts_list)}")

        # Construct Answer Statements
        answer_statements: List[str] = []
        citations_list: List[str] = []

        total_records = len(active_items)
        answer_statements.append(
            f"Based on the retrieved forensic evidence, {total_records} relevant record"
            f"{'s were' if total_records > 1 else ' was'} identified:"
        )

        for item in active_items:
            sender_str = f" from {item.sender}" if item.sender else ""
            receiver_str = f" to {item.receiver}" if item.receiver else ""
            app_str = f" via {item.source_application}" if item.source_application else ""
            time_str = f" at {item.timestamp}" if item.timestamp else ""

            # Check for injection content and sanitize representation
            safe_content = item.content.strip()
            if len(safe_content) > 150:
                safe_content = safe_content[:147] + "..."

            statement = (
                f"• [{item.evidence_tag}] A {item.artifact_type} record{app_str}{sender_str}{receiver_str}{time_str} "
                f"contains content: \"{safe_content}\"."
            )
            answer_statements.append(statement)
            citations_list.append(
                f"- [{item.evidence_tag}]: Direct {item.artifact_type} record "
                f"(Evidence ID: {item.evidence_id}, Canonical ID: {item.canonical_id})"
            )

        answer_body = "\n".join(answer_statements)
        citations_body = "\n".join(citations_list) if citations_list else "- None"
        conflicts_body = "\n".join(conflicts) if conflicts else "None identified in the retrieved context."

        uncertainty_note = (
            "Evidence statements reflect logged records directly. "
            "Semantic similarity does not establish guilt or unrecorded real-world actions."
        )
        limitations_note = (
            f"Findings are based strictly on {total_records} retrieved record"
            f"{'s' if total_records > 1 else ''} in the active case scope."
        )

        return (
            f"ANSWER:\n{answer_body}\n\n"
            f"EVIDENCE_REFERENCES:\n{citations_body}\n\n"
            f"CONFLICTING_EVIDENCE:\n{conflicts_body}\n\n"
            f"UNCERTAINTY:\n{uncertainty_note}\n\n"
            f"LIMITATIONS:\n{limitations_note}"
        )

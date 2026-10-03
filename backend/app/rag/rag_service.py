import logging
import time
from typing import Any, Dict, List, Optional
import uuid
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.config import settings
from backend.app.models.enums import AuditAction, SearchMode
from backend.app.models.user import User
from backend.app.nlp.nlp_pipeline import InvestigationNLPPipeline
from backend.app.rag.citation_validator import CitationValidationService
from backend.app.rag.context_builder import EvidenceContextBuilder
from backend.app.rag.conversation_manager import conversation_manager
from backend.app.rag.prompts import SYSTEM_PROMPT_FORENSIC_RAG, RAG_PROMPT_VERSION
from backend.app.rag.providers.factory import get_llm_provider
from backend.app.repositories.canonical_evidence_repo import CanonicalEvidenceRepository
from backend.app.schemas.rag import (
    RAGQueryRequest,
    RAGQueryResponse,
    ReproducibilityMetadata,
)
from backend.app.services.audit_service import AuditService
from backend.app.services.search_service import ForensicSearchService

logger = logging.getLogger(__name__)


class ForensicRAGService:
    """
    Orchestrates the complete Phase 12 Evidence-Grounded RAG Pipeline:
    1. NLP Query Understanding & Retrieval Planning (Phase 11)
    2. Case-Scoped Forensic Retrieval (Phase 9 & 10)
    3. Evidence Context Construction & Token Budgeting
    4. Multi-Turn Conversation Context Integration
    5. Evidence-Grounded LLM Generation
    6. Citation Extraction & Zero-Hallucination Validation
    7. Forensic Reproducibility Metadata & Audit Logging
    """

    def __init__(self, session: AsyncSession):
        self.session = session
        self.nlp_pipeline = InvestigationNLPPipeline()
        self.search_service = ForensicSearchService(session)
        self.canonical_repo = CanonicalEvidenceRepository(session)
        self.audit_service = AuditService(session)
        self.context_builder = EvidenceContextBuilder()
        self.citation_validator = CitationValidationService()

    async def execute_rag_query(
        self,
        case_id: UUID,
        current_user: User,
        request: RAGQueryRequest,
        client_ip: Optional[str] = None,
    ) -> RAGQueryResponse:
        t_start = time.monotonic()
        query_id = str(uuid.uuid4())
        case_id_str = str(case_id)
        conv_id = request.conversation_id or str(uuid.uuid4())

        # Step 1: Query Understanding & Investigation Planning (Phase 11)
        nlp_query = self.nlp_pipeline.parse_query(
            raw_query=request.query,
            case_id=case_id,
            user_requested_mode="HYBRID",
        )

        plan_dict = {
            "intent": nlp_query.intent.value if hasattr(nlp_query.intent, "value") else str(nlp_query.intent),
            "entities": [e.model_dump() for e in nlp_query.entities],
            "temporal_constraints": [t.model_dump() for t in nlp_query.temporal_constraints],
            "artifact_types": nlp_query.artifact_types,
            "search_text": nlp_query.search_text,
            "filters": nlp_query.filters.model_dump() if hasattr(nlp_query.filters, "model_dump") else nlp_query.filters,
            "recommended_mode": nlp_query.recommended_retrieval_mode,
        }

        # Step 2: Phase 9/10 Retrieval Execution
        search_mode = SearchMode.HYBRID
        if nlp_query.recommended_retrieval_mode:
            try:
                search_mode = SearchMode(nlp_query.recommended_retrieval_mode.upper())
            except Exception:
                search_mode = SearchMode.HYBRID

        # Determine search filters from plan
        search_text = nlp_query.search_text or request.query
        max_records = request.max_context_records or settings.RAG_MAX_CONTEXT_RECORDS

        start_time = None
        end_time = None
        if nlp_query.temporal_constraints:
            first_tc = nlp_query.temporal_constraints[0]
            start_time = first_tc.start_time
            end_time = first_tc.end_time

        search_response = await self.search_service.search(
            case_id=case_id,
            current_user=current_user,
            q=search_text,
            mode=search_mode,
            start_time=start_time,
            end_time=end_time,
            page_size=min(max_records * 2, 50),
            client_ip=client_ip,
        )

        # Step 3: Fetch full canonical record data for top candidates
        raw_evidence_candidates: List[Dict[str, Any]] = []
        for item in search_response.results:
            # Load canonical record for complete content
            canon_rec = await self.canonical_repo.get_by_id(item.id)
            if canon_rec and canon_rec.case_id == case_id:
                raw_evidence_candidates.append({
                    "canonical_id": str(canon_rec.id),
                    "evidence_id": str(canon_rec.evidence_id),
                    "raw_artifact_id": str(canon_rec.raw_artifact_id) if canon_rec.raw_artifact_id else None,
                    "case_id": str(canon_rec.case_id),
                    "artifact_type": str(canon_rec.artifact_type.value if hasattr(canon_rec.artifact_type, "value") else canon_rec.artifact_type),
                    "source_application": canon_rec.application,
                    "timestamp": canon_rec.event_timestamp.isoformat() if canon_rec.event_timestamp else None,
                    "content": canon_rec.content or item.content_preview or "",
                    "source_file": canon_rec.source_file,
                    "record_identifier": canon_rec.record_identifier,
                    "score": item.similarity_score or 1.0,
                    "sender": canon_rec.parsed_payload.get("sender") or canon_rec.parsed_payload.get("from") if canon_rec.parsed_payload else None,
                    "receiver": canon_rec.parsed_payload.get("receiver") or canon_rec.parsed_payload.get("to") if canon_rec.parsed_payload else None,
                })
            elif canon_rec is None:
                # Fallback to search result item
                raw_evidence_candidates.append({
                    "canonical_id": str(item.id),
                    "evidence_id": str(item.source.evidence_id),
                    "raw_artifact_id": str(item.source.raw_artifact_id) if item.source else None,
                    "case_id": case_id_str,
                    "artifact_type": str(item.artifact_type.value if hasattr(item.artifact_type, "value") else item.artifact_type),
                    "source_application": item.application,
                    "timestamp": item.event_timestamp.isoformat() if item.event_timestamp else None,
                    "content": item.content_preview or "",
                    "source_file": item.source.source_file if item.source else None,
                    "record_identifier": item.source.record_identifier if item.source else None,
                    "score": item.similarity_score or 1.0,
                })

        # Step 4: Controlled Context Construction & Deduplication
        context_items, context_text, tag_lookup, detected_conflicts = self.context_builder.build_context(
            raw_search_results=raw_evidence_candidates,
            case_id=case_id_str,
        )

        # Step 5: Prior Conversation History (Case-Isolated)
        conv_history_text = conversation_manager.format_history_for_prompt(
            case_id=case_id_str,
            conversation_id=conv_id,
        )

        # Step 6: Evidence-Grounded LLM Generation
        provider = get_llm_provider(
            provider_name=request.provider_override or settings.RAG_LLM_PROVIDER,
            model_name=settings.RAG_LLM_MODEL,
        )

        raw_llm_output = await provider.generate_answer(
            query=request.query,
            evidence_items=context_items,
            evidence_context_text=context_text,
            system_prompt=SYSTEM_PROMPT_FORENSIC_RAG,
            conversation_history_text=conv_history_text,
        )

        # Step 7: Citation Validation & Hallucination Defense
        valid_citations, validation_report, sanitized_output = self.citation_validator.validate_citations(
            raw_answer=raw_llm_output,
            tag_lookup=tag_lookup,
            active_case_id=case_id_str,
        )

        # Step 8: Parse Output Sections
        answer_text = sanitized_output
        uncertainty_text = None
        limitations_text = None
        is_insufficient = False

        if "ANSWER:" in sanitized_output:
            parts = sanitized_output.split("ANSWER:")
            remainder = parts[1] if len(parts) > 1 else sanitized_output

            # Extract sections if present
            if "EVIDENCE_REFERENCES:" in remainder:
                ans_part, ref_part = remainder.split("EVIDENCE_REFERENCES:", 1)
                answer_text = ans_part.strip()
                
                if "UNCERTAINTY:" in ref_part:
                    _, unc_part = ref_part.split("UNCERTAINTY:", 1)
                    if "LIMITATIONS:" in unc_part:
                        u_part, lim_part = unc_part.split("LIMITATIONS:", 1)
                        uncertainty_text = u_part.strip()
                        limitations_text = lim_part.strip()
                    else:
                        uncertainty_text = unc_part.strip()
            else:
                answer_text = remainder.strip()

        if "does not provide enough information" in answer_text.lower() or "insufficient" in answer_text.lower():
            is_insufficient = True

        # Step 9: Save Turns to Conversation Manager
        conversation_manager.add_turn(
            case_id=case_id_str,
            conversation_id=conv_id,
            role="user",
            content=request.query,
        )
        conversation_manager.add_turn(
            case_id=case_id_str,
            conversation_id=conv_id,
            role="assistant",
            content=answer_text,
            evidence_references=valid_citations,
        )

        # Latency calculation
        latency_ms = round((time.monotonic() - t_start) * 1000, 2)

        # Step 10: Reproducibility Metadata
        retrieved_ids = [item.evidence_id for item in context_items]
        reproducibility = ReproducibilityMetadata(
            query=request.query,
            case_id=case_id_str,
            llm_provider=provider.provider_name,
            llm_model=provider.model_name,
            temperature=settings.RAG_TEMPERATURE,
            prompt_version=RAG_PROMPT_VERSION,
            rag_version=settings.RAG_VERSION,
            retrieval_top_k=len(search_response.results),
            context_record_count=len(context_items),
            retrieved_evidence_ids=retrieved_ids,
            timestamp=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        )

        # Step 11: Audit Logging
        audit_log = await self.audit_service.record_event(
            action=AuditAction.RAG_QUERY_EXECUTED.value if hasattr(AuditAction.RAG_QUERY_EXECUTED, "value") else str(AuditAction.RAG_QUERY_EXECUTED),
            resource_type="rag_query",
            status="SUCCESS",
            user_id=current_user.id,
            resource_id=query_id,
            case_id=case_id,
            details={
                "query_id": query_id,
                "conversation_id": conv_id,
                "query": request.query,
                "llm_provider": provider.provider_name,
                "llm_model": provider.model_name,
                "retrieved_evidence_count": len(context_items),
                "retrieved_evidence_ids": retrieved_ids[:10],
                "citations_count": len(valid_citations),
                "is_insufficient_evidence": is_insufficient,
                "is_valid": validation_report.is_valid,
                "latency_ms": latency_ms,
            },
            client_ip=client_ip,
        )
        audit_log_id = str(audit_log.id) if audit_log else None

        return RAGQueryResponse(
            query_id=query_id,
            case_id=case_id_str,
            conversation_id=conv_id,
            query=request.query,
            investigation_plan=plan_dict,
            answer=answer_text,
            evidence_references=valid_citations,
            conflicting_evidence=detected_conflicts,
            uncertainty=uncertainty_text,
            limitations=limitations_text,
            is_insufficient_evidence=is_insufficient,
            validation_report=validation_report,
            reproducibility=reproducibility,
            audit_log_id=audit_log_id,
            latency_ms=latency_ms,
        )

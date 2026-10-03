"""
Phase 11 — Investigation NLP Pipeline

Unified NLP processing pipeline for forensic investigation queries:
Input Validation & Normalization → Entity Extraction → Temporal Parsing → Intent Classification → Query Planning.
"""

import logging
from typing import Optional
from uuid import UUID

from backend.app.core.config import settings
from backend.app.nlp.entity_extractor import ForensicEntityExtractor, get_spacy_nlp
from backend.app.nlp.intent_classifier import InvestigationIntentClassifier
from backend.app.nlp.query_normalizer import QueryNormalizer
from backend.app.nlp.query_planner import InvestigationQueryPlanner
from backend.app.nlp.temporal_parser import TemporalParser
from backend.app.schemas.investigation import (
    InvestigationQuery,
    InvestigationQueryInterpretation,
    InvestigationRetrievalPlan,
)

logger = logging.getLogger(__name__)


class InvestigationNLPPipeline:
    """Complete NLP parsing and query interpretation engine."""

    def __init__(self):
        self.normalizer = QueryNormalizer()
        self.entity_extractor = ForensicEntityExtractor(get_spacy_nlp())
        self.temporal_parser = TemporalParser()
        self.intent_classifier = InvestigationIntentClassifier()
        self.query_planner = InvestigationQueryPlanner()
        self.version = getattr(settings, "NLP_PARSER_VERSION", "1.0.0")

    def parse_query(
        self,
        raw_query: str,
        case_id: Optional[UUID] = None,
        user_requested_mode: Optional[str] = "AUTO"
    ) -> InvestigationQuery:
        """Execute full NLP pipeline on an investigator natural language query."""
        # Step 1: Input Validation & Text Normalization
        normalized_query, _ = self.normalizer.normalize(raw_query)

        # Step 2: Temporal Expression Extraction
        temporal_constraints = self.temporal_parser.extract_temporal_constraints(normalized_query)

        # Step 3: Forensic Entity Extraction (Regex, Lexicon, spaCy)
        entities = self.entity_extractor.extract_entities(normalized_query)

        # Step 4: Intent Classification
        intent = self.intent_classifier.classify(
            query=normalized_query,
            entities=entities,
            temporal_constraints=temporal_constraints
        )

        # Step 5: Query Constraint Construction & Retrieval Plan Generation
        plan = self.query_planner.plan(
            raw_query=normalized_query,
            intent=intent,
            entities=entities,
            temporal_constraints=temporal_constraints,
            user_requested_mode=user_requested_mode
        )

        # Step 6: Assemble Canonical InvestigationQuery Model
        artifact_types = [e.normalized_value for e in entities if e.type.value == "ARTIFACT_TYPE"]

        return InvestigationQuery(
            case_id=case_id or UUID("00000000-0000-0000-0000-000000000000"),
            raw_query=raw_query,
            normalized_query=normalized_query,
            intent=intent,
            entities=entities,
            temporal_constraints=temporal_constraints,
            artifact_types=artifact_types,
            filters=plan.filters,
            search_text=plan.search_text,
            recommended_retrieval_mode=plan.recommended_mode,
            parser_version=self.version
        )

    def get_interpretation(
        self,
        investigation_query: InvestigationQuery,
        plan: InvestigationRetrievalPlan
    ) -> InvestigationQueryInterpretation:
        """Construct user-facing query interpretation."""
        return InvestigationQueryInterpretation(
            intent=investigation_query.intent,
            entities=investigation_query.entities,
            temporal_constraints=investigation_query.temporal_constraints,
            artifact_types=investigation_query.artifact_types,
            filters=plan.filters,
            search_text=plan.search_text,
            recommended_mode=plan.recommended_mode
        )


# Global singleton instance
_NLP_PIPELINE: Optional[InvestigationNLPPipeline] = None


def get_nlp_pipeline() -> InvestigationNLPPipeline:
    """Get or instantiate global NLP pipeline singleton."""
    global _NLP_PIPELINE
    if _NLP_PIPELINE is None:
        _NLP_PIPELINE = InvestigationNLPPipeline()
    return _NLP_PIPELINE

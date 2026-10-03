"""
Phase 11 — Investigation Query Planner

Translates structured query interpretations into concrete ForensicSearchService execution plans.
Selects optimal retrieval mode (EXACT, LEXICAL, SEMANTIC, HYBRID) and constructs forensic filter parameters.
"""

import logging
import re
from typing import Any, Dict, List, Optional

from backend.app.models.enums import ArtifactType, EntityType, InvestigationIntent, SearchMode, TimestampPrecision
from backend.app.schemas.investigation import (
    ExtractedEntity,
    InvestigationIntentResult,
    InvestigationQueryInterpretation,
    InvestigationRetrievalPlan,
    TemporalConstraint,
)

logger = logging.getLogger(__name__)

# Words to filter out when constructing residual search text
STOP_PHRASES = [
    r'\b(?:find|search|show|get|look for|list|display|retrieve)\b',
    r'\b(?:all|any|the|a|an|of|in|on|at|by|from|to|with|and|or|between)\b',
    r'\b(?:messages?|calls?|emails?|chats?|activity|activities|records?|evidence|events?|history)\b',
    r'\b(?:yesterday|today|tomorrow|last week|this month|morning|evening|night|afternoon)\b',
    r'\b(?:involving|sent|received|sent by|received by|created|happened|occurred|associated with|related to|mentioning|containing)\b',
]


class InvestigationQueryPlanner:
    """Generates execution plans and filter constraints for the Phase 9/10 Forensic Retrieval Engine."""

    def plan(
        self,
        raw_query: str,
        intent: InvestigationIntentResult,
        entities: List[ExtractedEntity],
        temporal_constraints: List[TemporalConstraint],
        user_requested_mode: Optional[str] = "AUTO"
    ) -> InvestigationRetrievalPlan:
        """Construct structured retrieval plan from parsed query components."""
        filters: Dict[str, Any] = {}
        
        # 1. Extract Artifact Types
        artifact_types: List[str] = []
        for ent in entities:
            if ent.type == EntityType.ARTIFACT_TYPE:
                artifact_types.append(ent.normalized_value)
                if "artifact_type" not in filters:
                    filters["artifact_type"] = ent.normalized_value

        # 2. Extract Application Filter
        apps = [e for e in entities if e.type == EntityType.APPLICATION]
        if apps:
            filters["application"] = apps[0].normalized_value

        # 3. Extract Device Filter
        devices = [e for e in entities if e.type == EntityType.DEVICE]
        if devices:
            filters["device_id"] = devices[0].normalized_value

        # 4. Extract Entity Filters (Phone, Email, Person, Account)
        phones = [e for e in entities if e.type == EntityType.PHONE_NUMBER]
        emails = [e for e in entities if e.type == EntityType.EMAIL]
        persons = [e for e in entities if e.type == EntityType.PERSON]
        accounts = [e for e in entities if e.type == EntityType.ACCOUNT]
        locations = [e for e in entities if e.type == EntityType.LOCATION]

        if phones:
            filters["entity_type"] = EntityType.PHONE_NUMBER.value
            filters["entity_value"] = phones[0].normalized_value
        elif emails:
            filters["entity_type"] = EntityType.EMAIL.value
            filters["entity_value"] = emails[0].normalized_value
        elif persons:
            filters["entity_type"] = EntityType.PERSON.value
            filters["entity_value"] = persons[0].normalized_value
        elif accounts:
            filters["entity_type"] = EntityType.ACCOUNT.value
            filters["entity_value"] = accounts[0].normalized_value

        # 5. Extract Temporal Constraints
        if temporal_constraints:
            tc = temporal_constraints[0]
            if tc.start_time:
                filters["start_time"] = tc.start_time.isoformat()
            if tc.end_time:
                filters["end_time"] = tc.end_time.isoformat()
            if tc.precision:
                filters["timestamp_precision"] = tc.precision

        # 6. Build Clean Search Text
        search_text = self._build_search_text(raw_query, entities, temporal_constraints)

        # 7. Determine Recommended Retrieval Mode
        recommended_mode, explanation = self._recommend_mode(
            intent=intent,
            entities=entities,
            temporal_constraints=temporal_constraints,
            search_text=search_text
        )

        # 8. Apply User Override if specified
        final_mode = recommended_mode
        if user_requested_mode and user_requested_mode.upper() != "AUTO":
            try:
                final_mode = SearchMode(user_requested_mode.upper())
            except ValueError:
                final_mode = recommended_mode

        return InvestigationRetrievalPlan(
            mode=final_mode,
            filters=filters,
            search_text=search_text,
            recommended_mode=recommended_mode,
            explanation=explanation
        )

    def _recommend_mode(
        self,
        intent: InvestigationIntentResult,
        entities: List[ExtractedEntity],
        temporal_constraints: List[TemporalConstraint],
        search_text: str
    ) -> (SearchMode, str):
        """Recommend search mode based on investigative intent and query specificity."""
        phones = [e for e in entities if e.type == EntityType.PHONE_NUMBER]
        devices = [e for e in entities if e.type == EntityType.DEVICE]
        emails = [e for e in entities if e.type == EntityType.EMAIL]

        # Exact mode for pure identifier lookups with no semantic query text
        if (len(phones) == 1 or len(devices) == 1 or len(emails) == 1) and not search_text and not temporal_constraints:
            return SearchMode.EXACT, "Direct identifier matching selected for exact forensic value lookup."

        # Lexical mode for keyword matching in specific artifacts
        if intent.type == InvestigationIntent.DEVICE_LOOKUP:
            return SearchMode.EXACT, "Device lookup matches structured device identifier fields."

        # Semantic mode for intent-heavy questions without specific keywords
        if intent.type in (InvestigationIntent.EVENT_RETRIEVAL, InvestigationIntent.TEMPORAL_INVESTIGATION) and not phones and not emails and len(search_text.split()) > 3:
            return SearchMode.SEMANTIC, "Dense vector semantic search recommended for descriptive event/timeline queries."

        # Hybrid default for comprehensive forensic recall (lexical precision + semantic similarity)
        return SearchMode.HYBRID, "Hybrid retrieval (Lexical + Semantic) recommended for optimal forensic precision and recall."

    def _build_search_text(
        self,
        query: str,
        entities: List[ExtractedEntity],
        temporal_constraints: List[TemporalConstraint]
    ) -> str:
        """Construct residual search string by cleaning query of boilerplate command words."""
        cleaned = query

        # Remove temporal raw text spans
        for tc in temporal_constraints:
            cleaned = cleaned.replace(tc.raw_text, " ")

        # Remove known applications and artifact words
        for ent in entities:
            if ent.type in (EntityType.APPLICATION, EntityType.ARTIFACT_TYPE):
                cleaned = cleaned.replace(ent.text, " ")

        # Remove common query stop phrases
        for pattern in STOP_PHRASES:
            cleaned = re.sub(pattern, " ", cleaned, flags=re.IGNORECASE)

        # Collapse whitespace
        cleaned = re.sub(r'\s+', ' ', cleaned).strip()

        # If everything was stripped, fall back to non-temporal entity texts or raw query
        if not cleaned:
            non_temp = [e.text for e in entities if e.type not in (EntityType.ARTIFACT_TYPE, EntityType.APPLICATION)]
            if non_temp:
                cleaned = " ".join(non_temp)
            else:
                cleaned = query.strip()

        return cleaned

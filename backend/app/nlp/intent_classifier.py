"""
Phase 11 — Investigation Intent Classifier

Configurable intent classification system for forensic investigation queries.
Maps natural-language queries and extracted entities into structured InvestigationIntent
with confidence scoring and forensic explanations.

Confidence scores represent model/rule certainty and strictly DO NOT imply guilt or criminality.
"""

import logging
import re
from typing import List, Optional, Tuple

from backend.app.models.enums import ArtifactType, EntityType, InvestigationIntent
from backend.app.schemas.investigation import (
    ExtractedEntity,
    InvestigationIntentResult,
    TemporalConstraint,
)

logger = logging.getLogger(__name__)


class InvestigationIntentClassifier:
    """Classifies natural language investigation queries into structured forensic intents."""

    def classify(
        self,
        query: str,
        entities: List[ExtractedEntity],
        temporal_constraints: List[TemporalConstraint]
    ) -> InvestigationIntentResult:
        """Classify query intent based on linguistic patterns and extracted entities."""
        query_clean = query.strip()
        query_lower = query_clean.lower()

        if not query_clean:
            return InvestigationIntentResult(
                type=InvestigationIntent.UNKNOWN,
                confidence=0.0,
                explanation="Empty query string."
            )

        # Entity counts by type
        phones = [e for e in entities if e.type == EntityType.PHONE_NUMBER]
        emails = [e for e in entities if e.type == EntityType.EMAIL]
        persons = [e for e in entities if e.type == EntityType.PERSON]
        accounts = [e for e in entities if e.type == EntityType.ACCOUNT]
        apps = [e for e in entities if e.type == EntityType.APPLICATION]
        devices = [e for e in entities if e.type == EntityType.DEVICE]
        locations = [e for e in entities if e.type == EntityType.LOCATION]
        artifacts = [e for e in entities if e.type == EntityType.ARTIFACT_TYPE]

        has_temporal = len(temporal_constraints) > 0

        # Rule 1: COMMUNICATION_ANALYSIS
        # Multi-party communication ("between X and Y", "calls between...", multiple phones/emails, or communication verbs)
        comm_keywords = {"communication", "communications", "communicating", "between", "conversation", "exchanged", "chatting", "calls between", "messages between"}
        has_comm_kw = any(kw in query_lower for kw in comm_keywords)
        
        if (len(phones) >= 2) or (len(emails) >= 2) or (has_comm_kw and (len(phones) >= 1 or len(persons) >= 1 or len(emails) >= 1 or "suspect" in query_lower)):
            confidence = 0.95 if (len(phones) >= 2 or len(emails) >= 2) else 0.88
            explanation = "Communication analysis between multiple identifiers or parties detected."
            return InvestigationIntentResult(
                type=InvestigationIntent.COMMUNICATION_ANALYSIS,
                confidence=confidence,
                explanation=explanation
            )

        # Rule 2: DEVICE_LOOKUP
        if devices or ("device" in query_lower or "imei" in query_lower or "mac address" in query_lower or "serial" in query_lower):
            if devices:
                return InvestigationIntentResult(
                    type=InvestigationIntent.DEVICE_LOOKUP,
                    confidence=0.92,
                    explanation=f"Device identifier inquiry targeting device '{devices[0].text}'."
                )
            elif re.search(r'\b(?:device|imei|serial)\b', query_lower):
                return InvestigationIntentResult(
                    type=InvestigationIntent.DEVICE_LOOKUP,
                    confidence=0.80,
                    explanation="Query referencing hardware/device identifier attributes."
                )

        # Rule 3: LOCATION_LOOKUP
        loc_keywords = {"location", "locations", "gps", "coordinate", "coordinates", "movement", "travel", "visited", "places", "where was"}
        has_loc_kw = any(kw in query_lower for kw in loc_keywords)
        if locations or has_loc_kw:
            confidence = 0.90 if locations else 0.82
            loc_str = locations[0].text if locations else "geographic criteria"
            return InvestigationIntentResult(
                type=InvestigationIntent.LOCATION_LOOKUP,
                confidence=confidence,
                explanation=f"Geographical location lookup for {loc_str}."
            )

        # Rule 4: APPLICATION_ACTIVITY
        if apps:
            confidence = 0.92
            app_names = ", ".join(a.normalized_value for a in apps)
            return InvestigationIntentResult(
                type=InvestigationIntent.APPLICATION_ACTIVITY,
                confidence=confidence,
                explanation=f"Application-specific activity query for {app_names}."
            )

        # Rule 5: PERSON_LOOKUP (Person names, single email, single phone, accounts)
        if persons or emails or accounts or (phones and not has_comm_kw) or ("involving" in query_lower):
            target = persons[0].text if persons else (emails[0].text if emails else (accounts[0].text if accounts else (phones[0].text if phones else "subject")))
            confidence = 0.90
            return InvestigationIntentResult(
                type=InvestigationIntent.PERSON_LOOKUP,
                confidence=confidence,
                explanation=f"Person / identifier inquiry targeting subject '{target}'."
            )

        # Rule 6: EVENT_RETRIEVAL
        event_keywords = {"event", "events", "incident", "happened during", "timeline"}
        has_event_kw = any(kw in query_lower for kw in event_keywords) or ("suspect" in query_lower and has_temporal)
        if has_event_kw and not (query_lower.startswith("what happened") and not "suspect" in query_lower):
            return InvestigationIntentResult(
                type=InvestigationIntent.EVENT_RETRIEVAL,
                confidence=0.85,
                explanation="Timeline event retrieval inquiry based on temporal or activity keywords."
            )

        # Rule 7: TEMPORAL_INVESTIGATION
        if has_temporal:
            time_str = temporal_constraints[0].raw_text
            return InvestigationIntentResult(
                type=InvestigationIntent.TEMPORAL_INVESTIGATION,
                confidence=0.88,
                explanation=f"Temporal timeline inquiry targeting time window '{time_str}'."
            )

        # Rule 8: GENERAL_EVIDENCE_SEARCH
        search_verbs = {"find", "search", "show", "get", "look for", "mentioning", "containing", "evidence"}
        has_search_verb = any(v in query_lower for v in search_verbs)
        if has_search_verb or len(query_clean.split()) >= 2:
            return InvestigationIntentResult(
                type=InvestigationIntent.GENERAL_EVIDENCE_SEARCH,
                confidence=0.75,
                explanation="General lexical/semantic forensic evidence search."
            )

        # Rule 9: UNKNOWN / UNSUPPORTED
        return InvestigationIntentResult(
            type=InvestigationIntent.UNKNOWN,
            confidence=0.30,
            explanation="Could not unambiguously classify investigative intent; defaulting to general search."
        )

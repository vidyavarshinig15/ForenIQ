"""
Phase 11 — Forensic Entity Extractor

Hybrid entity extraction combining deterministic regex patterns, canonical forensic
lexicons, and spaCy NER to identify forensic entities (PERSON, PHONE_NUMBER, EMAIL,
APPLICATION, ARTIFACT_TYPE, DEVICE, LOCATION, ACCOUNT, URL, etc.).
"""

import logging
import re
from typing import Dict, List, Optional, Set, Tuple

import spacy
from spacy.language import Language

from backend.app.core.config import settings
from backend.app.models.enums import ArtifactType, EntityType
from backend.app.normalizers.entities import (
    normalize_application_name,
    normalize_email,
    normalize_phone_number,
)
from backend.app.schemas.investigation import ExtractedEntity

logger = logging.getLogger(__name__)

# Global cached spaCy model
_SPACY_NLP: Optional[Language] = None


def get_spacy_nlp() -> Optional[Language]:
    """Get or lazily load the spaCy NLP pipeline."""
    global _SPACY_NLP
    if _SPACY_NLP is None:
        try:
            model_name = getattr(settings, "SPACY_MODEL_NAME", "en_core_web_sm")
            _SPACY_NLP = spacy.load(model_name, disable=["parser"])
            logger.info("Loaded spaCy model: %s", model_name)
        except Exception as e:
            logger.warning("Could not load spaCy model '%s': %s. Falling back to rule-based NER.", model_name, e)
            _SPACY_NLP = None
    return _SPACY_NLP


# Regex patterns for deterministic forensic extraction
EMAIL_PATTERN = re.compile(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b')
URL_PATTERN = re.compile(r'\b(?:https?://|www\.)[^\s<>"{}|\^~\[\]`]+\b', re.IGNORECASE)
PHONE_PATTERN = re.compile(
    r'(?:\+\d{1,3}[-.\s]?)?(?:\(?\d{2,4}\)?[-.\s]?)?\b\d{3,5}[-.\s]?\d{3,5}(?:[-.\s]?\d{2,4})?\b'
)
IMEI_PATTERN = re.compile(r'\b\d{15}\b')
MAC_ADDRESS_PATTERN = re.compile(r'\b(?:[0-9A-Fa-f]{2}[:-]){5}[0-9A-Fa-f]{2}\b')
DEVICE_ID_KEYWORD_PATTERN = re.compile(
    r'\b(?:device(?:\s+(?:imei|serial|id|number))?|serial|imei|mac(?:\s+address)?)\s+([A-Za-z0-9_\-]+)\b',
    re.IGNORECASE,
)
ACCOUNT_PATTERN = re.compile(r'(?:^|\s)(@[A-Za-z0-9_]{3,30})\b')

# Known forensic applications and their canonical forms
APPLICATION_LEXICON: Dict[str, str] = {
    "whatsapp": "WhatsApp",
    "telegram": "Telegram",
    "signal": "Signal",
    "facebook": "Facebook",
    "messenger": "Messenger",
    "fb messenger": "Messenger",
    "instagram": "Instagram",
    "wechat": "WeChat",
    "viber": "Viber",
    "skype": "Skype",
    "gmail": "Gmail",
    "outlook": "Outlook",
    "chrome": "Chrome",
    "safari": "Safari",
    "sms": "SMS",
    "mms": "MMS",
    "uber": "Uber",
    "truecaller": "Truecaller",
}

# Artifact type keywords matching ArtifactType enum
ARTIFACT_KEYWORDS: Dict[str, ArtifactType] = {
    "message": ArtifactType.MESSAGE,
    "messages": ArtifactType.MESSAGE,
    "chat": ArtifactType.MESSAGE,
    "chats": ArtifactType.MESSAGE,
    "sms": ArtifactType.MESSAGE,
    "text": ArtifactType.MESSAGE,
    "texts": ArtifactType.MESSAGE,
    "call": ArtifactType.CALL,
    "calls": ArtifactType.CALL,
    "calllog": ArtifactType.CALL,
    "call log": ArtifactType.CALL,
    "call logs": ArtifactType.CALL,
    "contact": ArtifactType.CONTACT,
    "contacts": ArtifactType.CONTACT,
    "phonebook": ArtifactType.CONTACT,
    "media": ArtifactType.FILESYSTEM,
    "photo": ArtifactType.FILESYSTEM,
    "photos": ArtifactType.FILESYSTEM,
    "image": ArtifactType.FILESYSTEM,
    "images": ArtifactType.FILESYSTEM,
    "video": ArtifactType.FILESYSTEM,
    "videos": ArtifactType.FILESYSTEM,
    "audio": ArtifactType.FILESYSTEM,
    "recording": ArtifactType.FILESYSTEM,
    "recordings": ArtifactType.FILESYSTEM,
    "location": ArtifactType.LOCATION,
    "locations": ArtifactType.LOCATION,
    "gps": ArtifactType.LOCATION,
    "coordinate": ArtifactType.LOCATION,
    "coordinates": ArtifactType.LOCATION,
    "browser": ArtifactType.BROWSER,
    "browsing": ArtifactType.BROWSER,
    "history": ArtifactType.BROWSER,
    "browsing history": ArtifactType.BROWSER,
    "web history": ArtifactType.BROWSER,
    "document": ArtifactType.FILESYSTEM,
    "documents": ArtifactType.FILESYSTEM,
    "file": ArtifactType.FILESYSTEM,
    "files": ArtifactType.FILESYSTEM,
    "calendar": ArtifactType.CALENDAR,
    "social": ArtifactType.SOCIAL,
}


class ForensicEntityExtractor:
    """Hybrid forensic entity extractor combining regex, lexicons, and spaCy NER."""

    def __init__(self, spacy_nlp: Optional[Language] = None):
        self.nlp = spacy_nlp or get_spacy_nlp()

    def extract_entities(self, query: str) -> List[ExtractedEntity]:
        """Extract all forensic entities from query text using hybrid approach."""
        if not query or not query.strip():
            return []

        raw_entities: List[ExtractedEntity] = []

        # 1. Deterministic Rule-Based Extraction
        raw_entities.extend(self._extract_emails(query))
        raw_entities.extend(self._extract_urls(query))
        raw_entities.extend(self._extract_phones(query))
        raw_entities.extend(self._extract_device_ids(query))
        raw_entities.extend(self._extract_accounts(query))
        raw_entities.extend(self._extract_applications(query))
        raw_entities.extend(self._extract_artifact_types(query))
        raw_entities.extend(self._extract_person_rules(query))

        # 2. NLP-Based Extraction (spaCy) for PERSON, LOCATION, ORG
        if self.nlp:
            raw_entities.extend(self._extract_spacy_entities(query))

        # 3. Span Resolution and Deduplication (Longest Match + Rule Priority)
        resolved_entities = self._resolve_overlapping_entities(raw_entities)

        # Sort by start_pos
        resolved_entities.sort(key=lambda e: (e.start_pos, -len(e.text)))
        return resolved_entities

    def _extract_emails(self, text: str) -> List[ExtractedEntity]:
        entities = []
        for match in EMAIL_PATTERN.finditer(text):
            val = match.group(0)
            norm, _ = normalize_email(val)
            entities.append(ExtractedEntity(
                type=EntityType.EMAIL,
                text=val,
                normalized_value=norm or val.lower(),
                start_pos=match.start(),
                end_pos=match.end(),
                extraction_method="PATTERN",
                confidence=0.99
            ))
        return entities

    def _extract_urls(self, text: str) -> List[ExtractedEntity]:
        entities = []
        for match in URL_PATTERN.finditer(text):
            val = match.group(0)
            entities.append(ExtractedEntity(
                type=EntityType.URL,
                text=val,
                normalized_value=val.strip().lower(),
                start_pos=match.start(),
                end_pos=match.end(),
                extraction_method="PATTERN",
                confidence=0.98
            ))
        return entities

    def _extract_phones(self, text: str) -> List[ExtractedEntity]:
        entities = []
        for match in PHONE_PATTERN.finditer(text):
            val = match.group(0).strip()
            # Ignore if length of actual digits is < 6 or it's a 4-digit year like "2024"
            digits_only = re.sub(r'\D', '', val)
            if len(digits_only) < 7 or (len(digits_only) <= 4 and (val.startswith("19") or val.startswith("20"))):
                continue
            
            # Avoid matching single time strings like 10:00:00
            if ":" in val:
                continue

            norm, _ = normalize_phone_number(val)
            entities.append(ExtractedEntity(
                type=EntityType.PHONE_NUMBER,
                text=val,
                normalized_value=norm or val,
                start_pos=match.start(),
                end_pos=match.end(),
                extraction_method="PATTERN",
                confidence=0.95
            ))
        return entities

    def _extract_device_ids(self, text: str) -> List[ExtractedEntity]:
        entities = []
        for match in IMEI_PATTERN.finditer(text):
            val = match.group(0)
            entities.append(ExtractedEntity(
                type=EntityType.DEVICE,
                text=val,
                normalized_value=val,
                start_pos=match.start(),
                end_pos=match.end(),
                extraction_method="PATTERN",
                confidence=0.95
            ))
        for match in MAC_ADDRESS_PATTERN.finditer(text):
            val = match.group(0)
            entities.append(ExtractedEntity(
                type=EntityType.DEVICE,
                text=val,
                normalized_value=val.upper(),
                start_pos=match.start(),
                end_pos=match.end(),
                extraction_method="PATTERN",
                confidence=0.98
            ))
        for match in DEVICE_ID_KEYWORD_PATTERN.finditer(text):
            val = match.group(1)
            entities.append(ExtractedEntity(
                type=EntityType.DEVICE,
                text=val,
                normalized_value=val.strip(),
                start_pos=match.start(1),
                end_pos=match.end(1),
                extraction_method="RULE",
                confidence=0.90
            ))
        return entities

    def _extract_accounts(self, text: str) -> List[ExtractedEntity]:
        entities = []
        for match in ACCOUNT_PATTERN.finditer(text):
            val = match.group(1).strip()
            clean_user = val.lstrip("@")
            entities.append(ExtractedEntity(
                type=EntityType.ACCOUNT,
                text=val,
                normalized_value=clean_user.lower(),
                start_pos=match.start(1),
                end_pos=match.end(1),
                extraction_method="PATTERN",
                confidence=0.92
            ))
        return entities

    def _extract_person_rules(self, text: str) -> List[ExtractedEntity]:
        entities = []
        # Match person names preceded by query prepositions
        person_rule = re.compile(r'\b(?:involving|sent by|from|named|by)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)\b')
        for match in person_rule.finditer(text):
            name_val = match.group(1).strip()
            # Avoid matching application names or days/months
            if name_val.lower() in APPLICATION_LEXICON or name_val.lower() in {
                "yesterday", "today", "tomorrow", "september", "october", "november",
                "december", "january", "february", "march", "april", "may", "june",
                "july", "august", "device", "user", "contact", "contacts", "message", "messages"
            }:
                continue
            entities.append(ExtractedEntity(
                type=EntityType.PERSON,
                text=name_val,
                normalized_value=name_val,
                start_pos=match.start(1),
                end_pos=match.end(1),
                extraction_method="RULE",
                confidence=0.90
            ))
        return entities

    def _extract_applications(self, text: str) -> List[ExtractedEntity]:
        entities = []
        text_lower = text.lower()
        for app_alias, canon_name in APPLICATION_LEXICON.items():
            pattern = rf'\b{re.escape(app_alias)}\b'
            for match in re.finditer(pattern, text_lower):
                val = text[match.start():match.end()]
                entities.append(ExtractedEntity(
                    type=EntityType.APPLICATION,
                    text=val,
                    normalized_value=canon_name,
                    start_pos=match.start(),
                    end_pos=match.end(),
                    extraction_method="LEXICON",
                    confidence=0.95
                ))
        return entities

    def _extract_artifact_types(self, text: str) -> List[ExtractedEntity]:
        entities = []
        text_lower = text.lower()
        for kw, art_type in ARTIFACT_KEYWORDS.items():
            pattern = rf'\b{re.escape(kw)}\b'
            for match in re.finditer(pattern, text_lower):
                val = text[match.start():match.end()]
                entities.append(ExtractedEntity(
                    type=EntityType.ARTIFACT_TYPE,
                    text=val,
                    normalized_value=art_type.value,
                    start_pos=match.start(),
                    end_pos=match.end(),
                    extraction_method="LEXICON",
                    confidence=0.95
                ))
        return entities

    def _extract_spacy_entities(self, text: str) -> List[ExtractedEntity]:
        entities = []
        try:
            doc = self.nlp(text)
            for ent in doc.ents:
                etype: Optional[EntityType] = None
                conf = 0.85

                if ent.label_ == "PERSON":
                    etype = EntityType.PERSON
                elif ent.label_ in ("GPE", "LOC"):
                    etype = EntityType.LOCATION
                elif ent.label_ == "ORG":
                    # If it matches an application, skip here (lexicon takes precedence)
                    if ent.text.lower() in APPLICATION_LEXICON:
                        continue
                    etype = EntityType.ORGANIZATION
                elif ent.label_ in ("DATE", "TIME"):
                    # Temporal parser handles dates/times, but record as fallback
                    continue
                else:
                    continue

                # Filter out stopwords or single common pronouns erroneously tagged as PERSON
                ent_text_clean = ent.text.strip()
                if ent_text_clean.lower() in {
                    "who", "what", "where", "when", "why", "how", "all", "find",
                    "show", "get", "search", "yesterday", "today", "tomorrow",
                    "september", "october", "november", "december", "january",
                    "february", "march", "april", "may", "june", "july", "august"
                }:
                    continue

                if etype:
                    entities.append(ExtractedEntity(
                        type=etype,
                        text=ent.text,
                        normalized_value=ent.text.strip(),
                        start_pos=ent.start_char,
                        end_pos=ent.end_char,
                        extraction_method="SPACY",
                        confidence=conf
                    ))
        except Exception as e:
            logger.warning("spaCy entity extraction failed: %s", e)
        return entities

    def _resolve_overlapping_entities(self, entities: List[ExtractedEntity]) -> List[ExtractedEntity]:
        """Resolve overlapping entity spans using method priority & span length."""
        if not entities:
            return []

        # Priority rank for extraction methods
        method_priority = {
            "PATTERN": 3,
            "LEXICON": 3,
            "RULE": 2,
            "SPACY": 1
        }

        # Deduplicate identical spans
        unique_map: Dict[Tuple[int, int, str], ExtractedEntity] = {}
        for ent in entities:
            key = (ent.start_pos, ent.end_pos, ent.type.value)
            if key not in unique_map or ent.confidence > unique_map[key].confidence:
                unique_map[key] = ent

        candidates = list(unique_map.values())
        # Sort by start_pos ascending, then span length descending
        candidates.sort(key=lambda e: (e.start_pos, -(e.end_pos - e.start_pos)))

        resolved: List[ExtractedEntity] = []
        for cand in candidates:
            # Check overlap with already accepted entities
            overlap = False
            for accepted in resolved:
                if max(cand.start_pos, accepted.start_pos) < min(cand.end_pos, accepted.end_pos):
                    # Overlap detected! Compare priority
                    cand_score = method_priority.get(cand.extraction_method, 1) * 10 + len(cand.text)
                    acc_score = method_priority.get(accepted.extraction_method, 1) * 10 + len(accepted.text)
                    if cand_score > acc_score:
                        resolved.remove(accepted)
                        resolved.append(cand)
                    overlap = True
                    break
            if not overlap:
                resolved.append(cand)

        return resolved

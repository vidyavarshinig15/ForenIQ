"""
Phase 11 — Query Normalizer & Sanitizer

Normalizes investigator natural language queries:
- NFKC Unicode normalization
- Control character and non-printable stripping
- Bounded whitespace consolidation
- Length truncation
- Injection protection
"""

import re
import unicodedata
from typing import Tuple

from backend.app.core.config import get_settings


class QueryNormalizer:
    """Sanitizes and normalizes raw investigator input strings."""

    @staticmethod
    def normalize(query: str) -> Tuple[str, str]:
        """
        Cleans and normalizes query text.
        
        Returns:
            (normalized_query, original_query)
        """
        if not query:
            return "", ""

        orig = str(query)
        settings = get_settings()

        # 1. Truncate oversized queries
        raw = orig[: settings.MAX_INVESTIGATION_QUERY_LENGTH]

        # 2. NFKC Unicode normalization
        normalized = unicodedata.normalize("NFKC", raw)

        # 3. Strip dangerous control characters (keep standard whitespace)
        normalized = "".join(ch for ch in normalized if ch == " " or ch == "\t" or ch == "\n" or not unicodedata.category(ch).startswith("C"))

        # 4. Collapse multiple whitespace characters into a single space
        normalized = re.sub(r"\s+", " ", normalized).strip()

        # 5. Remove null bytes or toxic escape sequences
        normalized = normalized.replace("\x00", "").replace("\r", "")

        return normalized, orig

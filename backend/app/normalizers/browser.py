from typing import Any, Dict, List, Optional

from backend.app.models.enums import ArtifactType, EntityType, TimestampStatus
from backend.app.models.raw_artifact import RawArtifact
from backend.app.normalizers.base import BaseArtifactNormalizer
from backend.app.normalizers.dto import NormalizedRecordDTO
from backend.app.normalizers.entities import create_entity_ref, normalize_application_name
from backend.app.normalizers.timestamps import normalize_timestamp


class BrowserNormalizer(BaseArtifactNormalizer):
    """
    Normalizes web history, visited URLs, bookmarks, and search logs.
    Captures visited destinations without inferring intent.
    """

    @property
    def artifact_type(self) -> ArtifactType:
        return ArtifactType.BROWSER

    def normalize(self, raw_artifact: RawArtifact) -> NormalizedRecordDTO:
        data = raw_artifact.raw_data or {}
        warnings: List[Dict[str, Any]] = []

        # 1. Timestamp Normalization
        ts_res = normalize_timestamp(data.get("timestamp"))
        if ts_res.status == TimestampStatus.INVALID:
            warnings.append(self.create_warning("timestamp", "INVALID_TIMESTAMP", f"Unable to parse timestamp: {data.get('timestamp')}"))

        # 2. URL & Browser Entities
        url_raw = data.get("url")
        url_str = str(url_raw).strip() if url_raw is not None else None
        if not url_str:
            warnings.append(self.create_warning("url", "MISSING_URL", "Browser record has no URL specified.", severity="ERROR"))

        title_raw = data.get("title")
        title_str = str(title_raw).strip() if title_raw is not None else None

        browser_raw = data.get("browser") or "Browser"
        canon_browser, orig_browser = normalize_application_name(browser_raw)

        entities: List[Dict[str, Any]] = []
        if url_str:
            entities.append(create_entity_ref(EntityType.URL, url_str, "visited_url", url_str))
        if canon_browser:
            entities.append(create_entity_ref(EntityType.APPLICATION, orig_browser or canon_browser, "browser", canon_browser))

        # 3. Visit Count
        visit_count_raw = data.get("visit_count")
        visit_count: Optional[int] = None
        if visit_count_raw is not None:
            try:
                visit_count = int(visit_count_raw)
            except (ValueError, TypeError):
                pass

        # 4. Content Synthesis
        if title_str and url_str:
            content = f"{title_str} ({url_str})"
        elif url_str:
            content = url_str
        elif title_str:
            content = title_str
        else:
            content = "Empty Browser History Entry"

        metadata = {
            "url": url_str,
            "title": title_str,
            "browser": canon_browser,
            "visit_count": visit_count,
            "source_tag": data.get("source_tag"),
        }

        has_critical = url_str is None
        quality_status = self.calculate_quality_status(warnings, has_critical_missing=has_critical)

        return NormalizedRecordDTO(
            artifact_type=self.artifact_type,
            source_file=raw_artifact.source_file,
            source_path=raw_artifact.source_path,
            record_identifier=raw_artifact.record_identifier,
            event_timestamp=ts_res.normalized_utc,
            timestamp_precision=ts_res.precision,
            timestamp_status=ts_res.status,
            original_timestamp=ts_res.original_timestamp,
            original_timezone=ts_res.original_timezone,
            application=canon_browser,
            original_application=orig_browser,
            content=content,
            entities=entities,
            metadata=metadata,
            data_quality_status=quality_status,
            validation_warnings=warnings,
            parser_version="1.0.0",
            normalizer_version="1.0.0",
        )

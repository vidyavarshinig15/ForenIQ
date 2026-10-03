"""
Phase 10 — Embedding Formatter & Content Hashing

Generates deterministic, forensic-grade textual representations of CanonicalEvidence records
prior to vector embedding. Calculates deterministic SHA-256 content hashes to detect
staleness when canonical evidence is modified or reprocessed.
"""

import hashlib
import json
from typing import Optional, Tuple
from backend.app.models.canonical_evidence import CanonicalEvidence
from backend.app.models.enums import ArtifactType


class EmbeddingFormatter:
    """Formats CanonicalEvidence records into structured text for semantic indexing."""

    @staticmethod
    def format_canonical_record(record: CanonicalEvidence) -> Tuple[Optional[str], Optional[str]]:
        """
        Converts a CanonicalEvidence entity into a deterministic textual representation
        and its SHA-256 content hash.
        
        Returns:
            (formatted_text, sha256_hash) if embeddable, or (None, None) if not embeddable.
        """
        artifact_type = record.artifact_type
        text_parts = [f"Artifact Type: {artifact_type.value if hasattr(artifact_type, 'value') else artifact_type}"]

        if record.application:
            text_parts.append(f"Application: {record.application.strip()}")

        if record.event_timestamp:
            ts_str = record.event_timestamp.isoformat() if hasattr(record.event_timestamp, "isoformat") else str(record.event_timestamp)
            text_parts.append(f"Timestamp: {ts_str}")

        if record.device_id:
            text_parts.append(f"Device: {record.device_id.strip()}")

        if record.source_file:
            text_parts.append(f"Source File: {record.source_file.strip()}")

        # Content text (primary signal)
        content_text = (record.content or "").strip()
        if content_text:
            text_parts.append(f"Content: {content_text}")

        # Structured entities
        if record.entities:
            entity_str_list = []
            for ent in record.entities:
                if isinstance(ent, dict):
                    e_type = ent.get("type", "ENTITY")
                    e_val = ent.get("value", "")
                    if e_val:
                        entity_str_list.append(f"{e_type}: {e_val}")
            if entity_str_list:
                text_parts.append(f"Entities: {', '.join(entity_str_list)}")

        # Artifact-specific fields
        raw_meta = getattr(record, "metadata_", None) or getattr(record, "metadata_json", None) or {}
        if isinstance(raw_meta, dict) and raw_meta:
            meta = raw_meta
            # Sender / Receiver
            sender = meta.get("sender") or meta.get("from") or meta.get("caller") or meta.get("source")
            receiver = meta.get("receiver") or meta.get("to") or meta.get("recipient") or meta.get("destination")
            if sender:
                text_parts.append(f"Sender: {sender}")
            if receiver:
                text_parts.append(f"Receiver: {receiver}")

            # Specific attributes
            if "url" in meta and meta["url"]:
                text_parts.append(f"URL: {meta['url']}")
            if "title" in meta and meta["title"]:
                text_parts.append(f"Title: {meta['title']}")
            if "duration_seconds" in meta and meta["duration_seconds"]:
                text_parts.append(f"Duration: {meta['duration_seconds']}s")
            if "status" in meta and meta["status"]:
                text_parts.append(f"Status: {meta['status']}")
            if "location_name" in meta and meta["location_name"]:
                text_parts.append(f"Location Name: {meta['location_name']}")
            if "latitude" in meta and "longitude" in meta:
                text_parts.append(f"Coordinates: {meta['latitude']}, {meta['longitude']}")

        # Check embeddability: must have more than just artifact type / boilerplate
        meaningful_payload = content_text or (record.entities and len(record.entities) > 0) or bool(raw_meta)
        if not meaningful_payload:
            return None, None

        formatted_text = "\n".join(text_parts).strip()
        if len(formatted_text) < 15:
            return None, None

        content_hash = hashlib.sha256(formatted_text.encode("utf-8")).hexdigest()
        return formatted_text, content_hash

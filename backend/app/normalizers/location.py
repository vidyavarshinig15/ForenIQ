from typing import Any, Dict, List, Optional

from backend.app.models.enums import ArtifactType, DataQualityStatus, EntityType, TimestampStatus
from backend.app.models.raw_artifact import RawArtifact
from backend.app.normalizers.base import BaseArtifactNormalizer
from backend.app.normalizers.dto import NormalizedRecordDTO
from backend.app.normalizers.entities import create_entity_ref
from backend.app.normalizers.timestamps import normalize_timestamp


class LocationNormalizer(BaseArtifactNormalizer):
    """
    Normalizes forensic geolocation records, GPS tracks, and cell tower coordinates.
    Strictly enforces coordinate bounds without silent correction of corrupted inputs.
    """

    @property
    def artifact_type(self) -> ArtifactType:
        return ArtifactType.LOCATION

    def normalize(self, raw_artifact: RawArtifact) -> NormalizedRecordDTO:
        data = raw_artifact.raw_data or {}
        warnings: List[Dict[str, Any]] = []

        # 1. Timestamp Normalization
        ts_res = normalize_timestamp(data.get("timestamp"))
        if ts_res.status == TimestampStatus.INVALID:
            warnings.append(self.create_warning("timestamp", "INVALID_TIMESTAMP", f"Unable to parse timestamp: {data.get('timestamp')}"))

        # 2. Coordinates Validation
        lat_raw = data.get("latitude")
        lon_raw = data.get("longitude")

        lat_val: Optional[float] = None
        lon_val: Optional[float] = None
        coords_valid = True

        if lat_raw is None or lon_raw is None:
            warnings.append(self.create_warning("coordinates", "MISSING_COORDINATES", "Latitude or longitude is missing.", severity="ERROR"))
            coords_valid = False
        else:
            try:
                lat_val = float(lat_raw)
                if not (-90.0 <= lat_val <= 90.0):
                    warnings.append(self.create_warning("latitude", "INVALID_LATITUDE_RANGE", f"Latitude {lat_val} outside [-90, 90]", severity="ERROR"))
                    coords_valid = False
            except (ValueError, TypeError):
                warnings.append(self.create_warning("latitude", "MALFORMED_LATITUDE", f"Non-numeric latitude: {lat_raw}", severity="ERROR"))
                coords_valid = False

            try:
                lon_val = float(lon_raw)
                if not (-180.0 <= lon_val <= 180.0):
                    warnings.append(self.create_warning("longitude", "INVALID_LONGITUDE_RANGE", f"Longitude {lon_val} outside [-180, 180]", severity="ERROR"))
                    coords_valid = False
            except (ValueError, TypeError):
                warnings.append(self.create_warning("longitude", "MALFORMED_LONGITUDE", f"Non-numeric longitude: {lon_raw}", severity="ERROR"))
                coords_valid = False

        # 3. Accuracy & Altitude
        acc_raw = data.get("accuracy")
        acc_val: Optional[float] = None
        if acc_raw is not None:
            try:
                acc_val = float(acc_raw)
            except (ValueError, TypeError):
                warnings.append(self.create_warning("accuracy", "INVALID_ACCURACY", f"Non-numeric accuracy: {acc_raw}"))

        alt_raw = data.get("altitude")
        alt_val: Optional[float] = None
        if alt_raw is not None:
            try:
                alt_val = float(alt_raw)
            except (ValueError, TypeError):
                pass

        provider = str(data.get("source") or data.get("provider") or "GPS")

        # 4. Entities
        entities: List[Dict[str, Any]] = []
        if coords_valid and lat_val is not None and lon_val is not None:
            entities.append(create_entity_ref(
                EntityType.LOCATION,
                f"{lat_val:.6f},{lon_val:.6f}",
                "coordinates",
                f"{lat_val:.6f},{lon_val:.6f}"
            ))

        # 5. Content Synthesis
        if coords_valid and lat_val is not None and lon_val is not None:
            acc_str = f"±{acc_val:.1f}m" if acc_val is not None else "accuracy unknown"
            content = f"Location Fix: {lat_val:.6f}, {lon_val:.6f} [{acc_str}, Provider: {provider}]"
        else:
            content = f"Invalid Location Fix: lat={lat_raw}, lon={lon_raw} [Provider: {provider}]"

        metadata = {
            "latitude": lat_val,
            "longitude": lon_val,
            "latitude_raw": lat_raw,
            "longitude_raw": lon_raw,
            "accuracy": acc_val,
            "altitude": alt_val,
            "provider": provider,
            "source_tag": data.get("source_tag"),
        }

        quality_status = self.calculate_quality_status(warnings, has_critical_missing=not coords_valid)

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
            application=provider,
            original_application=data.get("source"),
            content=content,
            entities=entities,
            metadata=metadata,
            data_quality_status=quality_status,
            validation_warnings=warnings,
            parser_version="1.0.0",
            normalizer_version="1.0.0",
        )

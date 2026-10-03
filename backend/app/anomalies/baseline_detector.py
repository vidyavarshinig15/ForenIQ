import logging
from typing import Any, Dict, List, Optional, Tuple
from uuid import UUID
import numpy as np

from backend.app.anomalies.feature_extractor import TemporalFeatureExtractor
from backend.app.models.enums import (
    AnomalyAlgorithm,
    AnomalyClassification,
    AnomalySeverity,
    AnomalyType,
)
from backend.app.schemas.timeline_anomaly import (
    AnomalyResult,
    BaselineComparisonMetric,
    TemporalWindowFeature,
)

logger = logging.getLogger(__name__)


class StatisticalBaselineDetector:
    """
    Parametric Baseline Anomaly Detector (Z-Score / IQR Thresholding).
    Used as a comparative baseline benchmark against multidimensional Isolation Forest.
    """

    def __init__(self, z_threshold: float = 2.5):
        self.z_threshold = z_threshold
        self.feature_names = TemporalFeatureExtractor.FEATURE_NAMES

    def detect_anomalies(
        self,
        case_id: UUID,
        analysis_windows: List[TemporalWindowFeature],
        baseline_profile: Dict[str, Dict[str, float]],
        evidence_id_map: Optional[Dict[str, UUID]] = None,
    ) -> List[AnomalyResult]:
        """
        Identify univariate outlier windows exceeding statistical Z-score thresholds.
        """
        anomalies: List[AnomalyResult] = []

        for window in analysis_windows:
            metrics: List[BaselineComparisonMetric] = []
            max_z = 0.0
            dominant_feat = "event_count"

            for feat in self.feature_names:
                obs = float(getattr(window, feat, 0.0))
                base_info = baseline_profile.get(feat, {"median": 0.0, "mean": 0.0, "std": 1.0})
                med = base_info["median"]
                mean = base_info["mean"]
                std = base_info["std"] if base_info["std"] > 1e-4 else 1.0

                z_score = abs(obs - mean) / std
                dev_factor = (obs / med) if med > 0 else (obs if obs > 0 else 1.0)

                metric = BaselineComparisonMetric(
                    feature_name=feat,
                    observed_value=round(obs, 2),
                    baseline_median=round(med, 2),
                    baseline_mean=round(mean, 2),
                    baseline_std=round(std, 2),
                    z_score=round(z_score, 2),
                    deviation_factor=round(dev_factor, 2),
                )
                metrics.append(metric)

                if z_score > max_z:
                    max_z = z_score
                    dominant_feat = feat

            if max_z >= self.z_threshold:
                # Map z_score to [0.5, 1.0] anomaly score
                anomaly_score = min(1.0, 0.5 + (max_z / 10.0))

                if dominant_feat in ["burst_frequency", "communication_count"]:
                    anom_type = AnomalyType.COMMUNICATION_BURST
                elif dominant_feat == "app_activity_count":
                    anom_type = AnomalyType.UNUSUAL_APPLICATION_ACTIVITY
                elif dominant_feat == "unique_contacts":
                    anom_type = AnomalyType.UNUSUAL_CONTACT_DIVERSITY
                elif dominant_feat == "time_of_day_hour":
                    anom_type = AnomalyType.UNUSUAL_TIME_OF_DAY
                else:
                    anom_type = AnomalyType.UNUSUAL_EVENT_FREQUENCY

                if anomaly_score >= 0.85:
                    severity = AnomalySeverity.HIGH_ANOMALY
                elif anomaly_score >= 0.70:
                    severity = AnomalySeverity.MODERATE_ANOMALY
                else:
                    severity = AnomalySeverity.LOW_ANOMALY

                explanation = (
                    f"Z-Score outlier detected: {dominant_feat} observed value {getattr(window, dominant_feat)} "
                    f"deviated from baseline mean with z-score {round(max_z, 2)} (threshold: {self.z_threshold})."
                )

                evidence_ids = []
                if evidence_id_map:
                    for ev_id in window.supporting_event_ids:
                        if ev_id in evidence_id_map:
                            evidence_ids.append(evidence_id_map[ev_id])

                anomaly_id = f"z_anom_{case_id}_{window.window_id}"
                anomalies.append(
                    AnomalyResult(
                        anomaly_id=anomaly_id,
                        case_id=case_id,
                        start_time=window.start_time,
                        end_time=window.end_time,
                        anomaly_type=anom_type,
                        anomaly_score=round(anomaly_score, 4),
                        classification=AnomalyClassification.ANOMALOUS,
                        severity=severity,
                        algorithm=AnomalyAlgorithm.STATISTICAL_ZSCORE,
                        model_parameters={"z_threshold": self.z_threshold, "max_z_score": round(max_z, 2)},
                        baseline_metrics=metrics,
                        factual_explanation=explanation,
                        supporting_event_ids=window.supporting_event_ids,
                        supporting_artifact_ids=window.supporting_artifact_ids,
                        supporting_evidence_ids=list(set(evidence_ids)),
                        entities_involved=window.entities_involved,
                        applications_involved=window.applications_involved,
                    )
                )

        anomalies.sort(key=lambda x: x.anomaly_score, reverse=True)
        return anomalies

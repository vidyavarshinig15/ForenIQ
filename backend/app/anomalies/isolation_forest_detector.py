import logging
from typing import Any, Dict, List, Optional, Tuple
from uuid import UUID
import numpy as np
from sklearn.ensemble import IsolationForest

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


class ForensicIsolationForestDetector:
    """
    Isolation Forest Statistical Anomaly Detector.
    Identifies multidimensional behavioural and temporal anomalies across forensic time windows.
    Strictly outputs statistical anomaly scores without criminal inference or guilt prediction.
    """

    def __init__(
        self,
        n_estimators: int = 100,
        contamination: float = 0.05,
        random_state: int = 42,
        score_threshold: float = 0.65,
    ):
        self.n_estimators = n_estimators
        self.contamination = contamination
        self.random_state = random_state
        self.score_threshold = score_threshold
        self.feature_names = TemporalFeatureExtractor.FEATURE_NAMES

    def _feature_matrix(self, windows: List[TemporalWindowFeature]) -> np.ndarray:
        """Transform window objects into a 2D float NumPy matrix."""
        matrix = []
        for w in windows:
            row = [float(getattr(w, f, 0.0)) for f in self.feature_names]
            matrix.append(row)
        return np.array(matrix, dtype=float)

    def _determine_anomaly_type_and_metrics(
        self,
        window: TemporalWindowFeature,
        baseline_profile: Dict[str, Dict[str, float]],
    ) -> Tuple[AnomalyType, List[BaselineComparisonMetric], str]:
        """
        Identify the primary contributing feature deviation and build factual explanations.
        """
        metrics: List[BaselineComparisonMetric] = []
        max_z_score = -1.0
        dominant_feature = "event_count"

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

            if z_score > max_z_score:
                max_z_score = z_score
                dominant_feature = feat

        # Categorize Anomaly Type based on dominant feature and context
        if dominant_feature in ["burst_frequency", "communication_count", "incoming_count", "outgoing_count"]:
            if window.communication_count > 0:
                anomaly_type = AnomalyType.COMMUNICATION_BURST
            else:
                anomaly_type = AnomalyType.COMMUNICATION_INACTIVITY
        elif dominant_feature == "app_activity_count":
            anomaly_type = AnomalyType.UNUSUAL_APPLICATION_ACTIVITY
        elif dominant_feature == "unique_contacts":
            anomaly_type = AnomalyType.UNUSUAL_CONTACT_DIVERSITY
        elif dominant_feature == "time_of_day_hour" or (window.time_of_day_hour in [0, 1, 2, 3, 4] and window.event_count > 0):
            anomaly_type = AnomalyType.UNUSUAL_TIME_OF_DAY
        elif dominant_feature == "inter_event_time_avg":
            anomaly_type = AnomalyType.UNUSUAL_INTER_EVENT_TIMING
        elif dominant_feature == "location_change_count":
            anomaly_type = AnomalyType.UNUSUAL_LOCATION_TRANSITION
        else:
            anomaly_type = AnomalyType.UNUSUAL_EVENT_FREQUENCY

        # Generate strictly factual non-speculative explanation
        dom_metric = next((m for m in metrics if m.feature_name == dominant_feature), metrics[0])
        explanation = (
            f"Statistically unusual pattern detected: {dom_metric.observed_value} {dominant_feature} "
            f"observed (baseline median: {dom_metric.baseline_median}, mean: {dom_metric.baseline_mean}, "
            f"z-score: {dom_metric.z_score})."
        )

        return anomaly_type, metrics, explanation

    def detect_anomalies(
        self,
        case_id: UUID,
        analysis_windows: List[TemporalWindowFeature],
        baseline_windows: List[TemporalWindowFeature],
        baseline_profile: Dict[str, Dict[str, float]],
        evidence_id_map: Optional[Dict[str, UUID]] = None,
    ) -> List[AnomalyResult]:
        """
        Fit Isolation Forest and score each time window.
        Returns sorted anomaly results with evidence traceability.
        """
        if not analysis_windows:
            return []

        # Prepare training data (baseline windows + analysis windows)
        training_windows = baseline_windows if baseline_windows else analysis_windows
        X_train = self._feature_matrix(training_windows)
        X_eval = self._feature_matrix(analysis_windows)

        # Fit Isolation Forest
        model = IsolationForest(
            n_estimators=self.n_estimators,
            contamination=self.contamination,
            random_state=self.random_state,
        )
        model.fit(X_train)

        # Decision function: lower values mean more anomalous
        raw_scores = model.decision_function(X_eval)

        # Normalize score into [0.0, 1.0] where 1.0 is most anomalous
        # Empirical decision_function typically sits in [-0.5, 0.5]
        min_s = float(np.min(raw_scores))
        max_s = float(np.max(raw_scores))
        score_range = max_s - min_s if max_s > min_s else 1.0

        normalized_scores = 1.0 - ((raw_scores - min_s) / score_range)

        anomalies: List[AnomalyResult] = []

        for idx, window in enumerate(analysis_windows):
            norm_score = float(normalized_scores[idx])
            # Check if classified as anomalous
            is_anomalous = (norm_score >= self.score_threshold) or (raw_scores[idx] < 0.0 and norm_score >= 0.50)

            if is_anomalous:
                anomaly_type, metrics, explanation = self._determine_anomaly_type_and_metrics(
                    window, baseline_profile
                )

                # Determine neutral severity tier
                if norm_score >= 0.85:
                    severity = AnomalySeverity.HIGH_ANOMALY
                elif norm_score >= 0.70:
                    severity = AnomalySeverity.MODERATE_ANOMALY
                else:
                    severity = AnomalySeverity.LOW_ANOMALY

                # Extract supporting evidence IDs
                evidence_ids = []
                if evidence_id_map:
                    for ev_id in window.supporting_event_ids:
                        if ev_id in evidence_id_map:
                            evidence_ids.append(evidence_id_map[ev_id])

                anomaly_id = f"anom_{case_id}_{window.window_id}"
                anomalies.append(
                    AnomalyResult(
                        anomaly_id=anomaly_id,
                        case_id=case_id,
                        start_time=window.start_time,
                        end_time=window.end_time,
                        anomaly_type=anomaly_type,
                        anomaly_score=round(norm_score, 4),
                        classification=AnomalyClassification.ANOMALOUS,
                        severity=severity,
                        algorithm=AnomalyAlgorithm.ISOLATION_FOREST,
                        model_parameters={
                            "n_estimators": self.n_estimators,
                            "contamination": self.contamination,
                            "random_state": self.random_state,
                            "raw_decision_score": round(float(raw_scores[idx]), 4),
                        },
                        baseline_metrics=metrics,
                        factual_explanation=explanation,
                        supporting_event_ids=window.supporting_event_ids,
                        supporting_artifact_ids=window.supporting_artifact_ids,
                        supporting_evidence_ids=list(set(evidence_ids)),
                        entities_involved=window.entities_involved,
                        applications_involved=window.applications_involved,
                    )
                )

        # Sort descending by anomaly score
        anomalies.sort(key=lambda x: x.anomaly_score, reverse=True)
        return anomalies

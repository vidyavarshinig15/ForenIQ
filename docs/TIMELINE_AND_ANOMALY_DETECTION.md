# Phase 14 — Timeline Analysis, Anomaly Detection & Investigative Pattern Discovery

**AI-Driven Intelligent UFDR Analysis System for Advanced Digital Forensic Investigations**  
**Team:** Vidyavarshini G, Suhani A N, Vyshanth S U  
**Guide:** Dr. Prasad M R  

---

## 1. Executive Summary & Forensic Context
Phase 14 introduces a Unified Forensic Timeline Analysis and Statistical Anomaly Detection subsystem. Forensic extractions often contain disparate timestamped artifacts (call logs, SMS, chats, GPS coordinates, application executions, browser history, and filesystem interactions) spread across multiple devices and containers. 

Phase 14 normalizes and synchronizes these multi-source events into a unified chronological stream, partitions continuous timelines into discrete sliding temporal windows, extracts behavioral/communication features, and applies statistical outlier detection algorithms (Multivariate Isolation Forest and Univariate Z-Score baseline detectors) to identify unusual temporal patterns with complete evidence traceability.

```
UFDR Extractions (Calls, Messages, App Events, GPS, Browser, Filesystem)
      ↓
Canonical Forensic Normalization (Phase 7 Schema)
      ↓
Unified Case-Scoped Forensic Timeline (Deterministic Ordering)
      ↓
Temporal Window Slicing (1m, 5m, 15m, 30m, 1h, 6h, 24h)
      ↓
Multidimensional Feature Extraction (Burst frequency, Inter-event time, Contact diversity)
      ↓
Baseline Profile Calculation (Median, Mean, Standard Deviation, IQR)
      ↓
Statistical Anomaly Detection (Isolation Forest / Z-Score Baseline Comparator)
      ↓
Evidence-Grounded Factual Explanations (Strictly Non-Speculative)
      ↓
Interactive Timeline & Anomaly Dashboard (Cross-Navigation to Graph & Evidence)
```

---

## 2. Forensic Safety & Non-Speculative Standard

> [!IMPORTANT]
> **Strict Forensic Standards**:
> - An anomaly is **strictly a mathematical or statistical pattern deviation** relative to a configured baseline.
> - An anomaly MUST NOT be automatically interpreted as criminal activity, suspicious intent, or evidence of guilt.
> - The system strictly prohibits automated suspect ranking, criminal profiling, or guilt scoring.
> - Model anomaly scores represent decision function deviations in $[0.0, 1.0]$, NOT "crime probability" or "risk scores".
> - All explanations are purely factual and descriptive (e.g. *"18 communication events occurred within this 15-minute window, compared with a baseline median of 1 event."*).

---

## 3. Timeline Architecture & Models

### 3.1 Timeline Event Model (`TimelineEvent`)
- `event_id`: Deterministic case-scoped identifier (`{case_id}:{artifact_id}`).
- `case_id`, `evidence_id`, `artifact_id`, `raw_artifact_id`: Full provenance links.
- `timestamp`: Normalized ISO-8601 string.
- `timestamp_precision`: Granularity (`SECOND`, `MILLISECOND`, `MINUTE`, `HOUR`, `DAY`).
- `timestamp_status`: Quality state (`VALID`, `INVALID`, `UNKNOWN`).
- `timezone`: Original timezone offset.
- `event_type`: Artifact categorization (`CALL`, `MESSAGE`, `LOCATION`, `APPLICATION`, `BROWSER`, `FILESYSTEM`, etc.).
- `actor` / `target`: Normalized participant handles.
- `device`: Device identifier.
- `content_summary`: Sanitized preview snippet.
- `source_file` / `source_path`: Original container references.

### 3.2 Deterministic Ordering
Timeline events are sorted deterministically:
1. `CanonicalEvidence.event_timestamp ASC NULLS LAST`
2. `CanonicalEvidence.artifact_type ASC`
3. `CanonicalEvidence.id ASC`

---

## 4. Temporal Windowing & Feature Engineering

Timelines are partitioned into contiguous, fixed-duration temporal windows (e.g. 15 minutes). For each window, the following 11-dimensional feature vector is extracted:

| Feature Name | Description | Forensic Utility |
| :--- | :--- | :--- |
| `event_count` | Total forensic events in window | Overall activity density |
| `communication_count` | Number of calls and messages | Communication intensity |
| `incoming_count` | Number of incoming communication events | Inbound traffic |
| `outgoing_count` | Number of outgoing communication events | Outbound activity |
| `unique_contacts` | Cardinality of distinct actors and targets | Interaction spread |
| `app_activity_count` | Launches and application interactions | Device utilization |
| `location_change_count` | GPS fix updates | Physical movement frequency |
| `burst_frequency` | Events per minute inside window | Velocity and burstiness |
| `inter_event_time_avg` | Mean seconds between consecutive events | Rapid-fire interaction spacing |
| `time_of_day_hour` | Hour of window start ($0 \dots 23$) | Off-hours / nighttime patterns |
| `day_of_week` | Day index ($0 = \text{Mon} \dots 6 = \text{Sun}$) | Weekend vs. weekday patterns |

---

## 5. Statistical Anomaly Detection Models

### 5.1 Multivariate Isolation Forest
- Algorithm: `sklearn.ensemble.IsolationForest`
- Default Parameters: `n_estimators=100`, `contamination=0.05`, `random_state=42`.
- Decision Function Mapping: Raw scores $s \in [-0.5, 0.5]$ normalized to $[0.0, 1.0]$.
- Dominant Feature Identification: Detects the primary feature with maximum Z-score deviation against baseline profile to assign `AnomalyType`.

### 5.2 Parametric Baseline Comparator (Z-Score)
- Evaluates univariate $Z = \frac{|x - \mu|}{\sigma}$ per feature.
- Identifies single-variable threshold violations ($Z \ge 2.5$) for direct comparative benchmarking against Isolation Forest.

### 5.3 Anomaly Categories
- `COMMUNICATION_BURST`
- `COMMUNICATION_INACTIVITY`
- `UNUSUAL_APPLICATION_ACTIVITY`
- `UNUSUAL_EVENT_FREQUENCY`
- `UNUSUAL_TIME_OF_DAY`
- `UNUSUAL_CONTACT_DIVERSITY`
- `UNUSUAL_INTER_EVENT_TIMING`
- `UNUSUAL_LOCATION_TRANSITION`

---

## 6. API Reference

| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `GET` | `/api/v1/cases/{case_id}/timeline` | Retrieve chronological timeline events with query filters. |
| `POST` | `/api/v1/cases/{case_id}/timeline/query` | Advanced multi-filter timeline query (categories, date bounds). |
| `POST` | `/api/v1/cases/{case_id}/anomalies/detect` | Synchronous statistical anomaly detection across case timeline. |
| `GET` | `/api/v1/cases/{case_id}/anomalies/{anomaly_id}` | Detailed context and supporting evidence for a specific anomaly. |
| `POST` | `/api/v1/cases/{case_id}/anomalies/jobs` | Submit asynchronous anomaly detection job for large datasets. |
| `GET` | `/api/v1/cases/{case_id}/anomalies/jobs/{job_id}` | Poll progress and status of background anomaly job. |

from datetime import datetime, timedelta, timezone
import math
from typing import Any, Dict, List, Optional, Tuple
from uuid import UUID
import numpy as np

from backend.app.models.enums import ArtifactType, TemporalWindowSize
from backend.app.schemas.timeline_anomaly import TemporalWindowFeature, TimelineEvent


class TemporalFeatureExtractor:
    """
    Temporal Windowing & Feature Engineering Engine.
    Partitions continuous forensic timeline streams into discrete time windows and
    computes multi-dimensional behavioral, communication, and temporal features.
    """

    WINDOW_SECONDS_MAP = {
        TemporalWindowSize.ONE_MINUTE: 60,
        TemporalWindowSize.FIVE_MINUTES: 300,
        TemporalWindowSize.FIFTEEN_MINUTES: 900,
        TemporalWindowSize.THIRTY_MINUTES: 1800,
        TemporalWindowSize.ONE_HOUR: 3600,
        TemporalWindowSize.SIX_HOURS: 21600,
        TemporalWindowSize.TWENTY_FOUR_HOURS: 86400,
    }

    FEATURE_NAMES = [
        "event_count",
        "communication_count",
        "incoming_count",
        "outgoing_count",
        "unique_contacts",
        "app_activity_count",
        "location_change_count",
        "burst_frequency",
        "inter_event_time_avg",
        "time_of_day_hour",
        "day_of_week",
    ]

    @classmethod
    def get_window_seconds(cls, window_size: TemporalWindowSize | str) -> int:
        """Resolve window size enum or string to total seconds."""
        if isinstance(window_size, str):
            for k, v in cls.WINDOW_SECONDS_MAP.items():
                if k.value == window_size or k.name == window_size:
                    return v
            if window_size.endswith("m"):
                return int(window_size[:-1]) * 60
            elif window_size.endswith("h"):
                return int(window_size[:-1]) * 3600
            elif window_size.endswith("d"):
                return int(window_size[:-1]) * 86400
            return 900
        return cls.WINDOW_SECONDS_MAP.get(window_size, 900)

    @classmethod
    def slice_into_windows(
        cls,
        timeline_events: List[TimelineEvent],
        window_size: TemporalWindowSize | str = TemporalWindowSize.FIFTEEN_MINUTES,
        explicit_start: Optional[str] = None,
        explicit_end: Optional[str] = None,
    ) -> List[TemporalWindowFeature]:
        """
        Slice chronological timeline events into contiguous fixed-duration temporal windows.
        """
        if not timeline_events and not (explicit_start and explicit_end):
            return []

        # Parse and sort timestamped events
        valid_events: List[Tuple[datetime, TimelineEvent]] = []
        for e in timeline_events:
            if e.timestamp:
                try:
                    dt = datetime.fromisoformat(e.timestamp.replace("Z", "+00:00"))
                    if dt.tzinfo is None:
                        dt = dt.replace(tzinfo=timezone.utc)
                    valid_events.append((dt, e))
                except ValueError:
                    continue

        valid_events.sort(key=lambda x: x[0])

        if not valid_events and not (explicit_start and explicit_end):
            return []

        # Determine overall timeline bounds
        if explicit_start:
            start_dt = datetime.fromisoformat(explicit_start.replace("Z", "+00:00"))
        else:
            start_dt = valid_events[0][0]

        if explicit_end:
            end_dt = datetime.fromisoformat(explicit_end.replace("Z", "+00:00"))
        else:
            end_dt = valid_events[-1][0]

        if start_dt.tzinfo is None:
            start_dt = start_dt.replace(tzinfo=timezone.utc)
        if end_dt.tzinfo is None:
            end_dt = end_dt.replace(tzinfo=timezone.utc)

        window_sec = cls.get_window_seconds(window_size)
        window_delta = timedelta(seconds=window_sec)

        # Align start_dt to window boundary
        epoch = datetime(1970, 1, 1, tzinfo=timezone.utc)
        start_seconds = (start_dt - epoch).total_seconds()
        aligned_start_seconds = math.floor(start_seconds / window_sec) * window_sec
        curr_window_start = epoch + timedelta(seconds=aligned_start_seconds)

        if end_dt <= curr_window_start:
            end_dt = curr_window_start + window_delta

        windows: List[TemporalWindowFeature] = []
        event_idx = 0
        total_events_len = len(valid_events)

        while curr_window_start < end_dt or (curr_window_start <= end_dt and not windows):
            curr_window_end = curr_window_start + window_delta
            window_id = f"win_{int(curr_window_start.timestamp())}_{window_sec}"

            # Collect events belonging to current window
            win_events: List[TimelineEvent] = []
            win_timestamps: List[datetime] = []

            # Fast cursor scan
            scan_idx = event_idx
            while scan_idx < total_events_len:
                ev_dt, ev = valid_events[scan_idx]
                if ev_dt < curr_window_start:
                    scan_idx += 1
                    event_idx = scan_idx
                    continue
                elif ev_dt < curr_window_end:
                    win_events.append(ev)
                    win_timestamps.append(ev_dt)
                    scan_idx += 1
                else:
                    break

            # Compute features for window
            event_count = len(win_events)
            comm_count = 0
            incoming_count = 0
            outgoing_count = 0
            contacts_set = set()
            app_act_count = 0
            loc_count = 0
            entities_set = set()
            apps_set = set()
            art_ids: List[UUID] = []
            event_ids: List[str] = []

            for ev in win_events:
                art_ids.append(ev.artifact_id)
                event_ids.append(ev.event_id)

                if ev.actor:
                    contacts_set.add(ev.actor)
                    entities_set.add(ev.actor)
                if ev.target:
                    contacts_set.add(ev.target)
                    entities_set.add(ev.target)
                if ev.application:
                    apps_set.add(ev.application)

                meta = ev.metadata or {}
                direction = (meta.get("direction") or meta.get("call_type") or "").upper()

                if ev.event_type in [ArtifactType.CALL, ArtifactType.MESSAGE]:
                    comm_count += 1
                    if "INCOMING" in direction or "MISSED" in direction or "RECEIVED" in direction:
                        incoming_count += 1
                    elif "OUTGOING" in direction or "SENT" in direction:
                        outgoing_count += 1
                elif ev.event_type in [ArtifactType.APPLICATION, ArtifactType.BROWSER, ArtifactType.FILESYSTEM]:
                    app_act_count += 1
                elif ev.event_type == ArtifactType.LOCATION:
                    loc_count += 1

            # Burst frequency: events per minute
            burst_freq = event_count / (window_sec / 60.0)

            # Average inter-event time
            if len(win_timestamps) >= 2:
                deltas = [
                    (win_timestamps[i] - win_timestamps[i - 1]).total_seconds()
                    for i in range(1, len(win_timestamps))
                ]
                avg_inter_event = float(np.mean(deltas))
            else:
                avg_inter_event = 0.0

            time_of_day_hour = curr_window_start.hour
            day_of_week = curr_window_start.weekday()

            feature_obj = TemporalWindowFeature(
                window_id=window_id,
                start_time=curr_window_start.isoformat(),
                end_time=curr_window_end.isoformat(),
                event_count=event_count,
                communication_count=comm_count,
                incoming_count=incoming_count,
                outgoing_count=outgoing_count,
                unique_contacts=len(contacts_set),
                app_activity_count=app_act_count,
                location_change_count=loc_count,
                burst_frequency=round(burst_freq, 4),
                inter_event_time_avg=round(avg_inter_event, 2),
                time_of_day_hour=time_of_day_hour,
                day_of_week=day_of_week,
                supporting_event_ids=event_ids,
                supporting_artifact_ids=art_ids,
                entities_involved=sorted(list(entities_set)),
                applications_involved=sorted(list(apps_set)),
            )

            # We include all windows or non-empty windows; for dense timeline analysis,
            # we keep non-empty windows plus transition samples
            if event_count > 0 or len(windows) < 100:
                windows.append(feature_obj)

            curr_window_start = curr_window_end

            # Safety break
            if len(windows) >= 10000:
                break

        return windows

    @classmethod
    def compute_baseline_profile(
        cls,
        baseline_windows: List[TemporalWindowFeature],
    ) -> Dict[str, Dict[str, float]]:
        """
        Compute descriptive baseline metrics (median, mean, std, IQR) across baseline windows.
        """
        profile: Dict[str, Dict[str, float]] = {}
        if not baseline_windows:
            for feat in cls.FEATURE_NAMES:
                profile[feat] = {"median": 0.0, "mean": 0.0, "std": 1.0, "iqr": 0.0, "min": 0.0, "max": 0.0}
            return profile

        for feat in cls.FEATURE_NAMES:
            values = np.array([getattr(w, feat, 0.0) for w in baseline_windows], dtype=float)
            q75, q25 = np.percentile(values, [75, 25])
            iqr = q75 - q25
            std_val = float(np.std(values))
            profile[feat] = {
                "median": round(float(np.median(values)), 3),
                "mean": round(float(np.mean(values)), 3),
                "std": round(std_val if std_val > 1e-4 else 1.0, 3),
                "iqr": round(float(iqr), 3),
                "min": round(float(np.min(values)), 3),
                "max": round(float(np.max(values)), 3),
            }

        return profile

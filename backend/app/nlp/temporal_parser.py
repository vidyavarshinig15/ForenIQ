"""
Phase 11 — Forensic Temporal Expression Parser

Extracts relative and explicit temporal expressions from investigator queries,
converting them into structured start/end datetime constraints with explicit precision.
Preserves UTC / case timezone without inventing unwarranted forensic precision.
"""

from datetime import datetime, time, timedelta, timezone
import re
from typing import List, Optional, Tuple
from dateutil import parser as date_parser

from backend.app.schemas.investigation import TemporalConstraint


class TemporalParser:
    """Extracts and standardizes temporal queries for forensic investigation."""

    MONTH_NAMES = r"(?:jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|jun(?:e)?|jul(?:y)?|aug(?:ust)?|sep(?:tember)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)"

    @classmethod
    def parse_temporal_expressions(
        cls,
        text: str,
        reference_time: Optional[datetime] = None,
        case_timezone: str = "UTC",
    ) -> List[TemporalConstraint]:
        """
        Scans query text for temporal patterns and converts them into structured constraints.
        
        Args:
            text: Normalized query string.
            reference_time: Current investigation timestamp (defaults to UTC now).
            case_timezone: Timezone identifier.
        """
        now = reference_time or datetime.now(timezone.utc)
        results: List[TemporalConstraint] = []
        text_lower = text.lower()

        # ------------------------------------------------------------------ #
        # 1. Relative Day / Week / Month expressions                         #
        # ------------------------------------------------------------------ #

        if re.search(r"\byesterday\b", text_lower):
            y_date = (now - timedelta(days=1)).date()
            start = datetime.combine(y_date, time.min, tzinfo=timezone.utc)
            end = datetime.combine(y_date, time.max, tzinfo=timezone.utc)
            results.append(
                TemporalConstraint(
                    start_time=start,
                    end_time=end,
                    raw_text="yesterday",
                    timezone=case_timezone,
                    precision="DAY",
                )
            )

        elif re.search(r"\btoday\b", text_lower):
            t_date = now.date()
            start = datetime.combine(t_date, time.min, tzinfo=timezone.utc)
            end = datetime.combine(t_date, time.max, tzinfo=timezone.utc)
            results.append(
                TemporalConstraint(
                    start_time=start,
                    end_time=end,
                    raw_text="today",
                    timezone=case_timezone,
                    precision="DAY",
                )
            )

        elif re.search(r"\blast\s+week\b", text_lower):
            start = now - timedelta(days=7)
            results.append(
                TemporalConstraint(
                    start_time=start,
                    end_time=now,
                    raw_text="last week",
                    timezone=case_timezone,
                    precision="DAY",
                )
            )

        elif re.search(r"\bthis\s+month\b", text_lower):
            start = datetime(now.year, now.month, 1, 0, 0, 0, tzinfo=timezone.utc)
            results.append(
                TemporalConstraint(
                    start_time=start,
                    end_time=now,
                    raw_text="this month",
                    timezone=case_timezone,
                    precision="MONTH",
                )
            )

        elif re.search(r"\blast\s+month\b", text_lower):
            start = now - timedelta(days=30)
            results.append(
                TemporalConstraint(
                    start_time=start,
                    end_time=now,
                    raw_text="last month",
                    timezone=case_timezone,
                    precision="MONTH",
                )
            )

        # ------------------------------------------------------------------ #
        # 2. Date Ranges: "between X and Y", "from X to Y"                   #
        # ------------------------------------------------------------------ #

        # Match "between <date1> and <date2>"
        between_date_match = re.search(
            rf"\bbetween\s+({cls.MONTH_NAMES}\s+\d{{1,2}}(?:,\s*\d{{4}})?|\d{{1,2}}(?:st|nd|rd|th)?\s+{cls.MONTH_NAMES}(?:\s+\d{{4}})?|\d{{4}}-\d{{2}}-\d{{2}})\s+and\s+({cls.MONTH_NAMES}\s+\d{{1,2}}(?:,\s*\d{{4}})?|\d{{1,2}}(?:st|nd|rd|th)?\s+{cls.MONTH_NAMES}(?:\s+\d{{4}})?|\d{{4}}-\d{{2}}-\d{{2}})\b",
            text_lower,
            re.IGNORECASE,
        )
        if between_date_match:
            d1_str, d2_str = between_date_match.group(1), between_date_match.group(2)
            t1, t2 = cls._parse_date_pair(d1_str, d2_str, now.year)
            if t1 and t2:
                results.append(
                    TemporalConstraint(
                        start_time=t1,
                        end_time=t2,
                        raw_text=between_date_match.group(0),
                        timezone=case_timezone,
                        precision="DAY",
                    )
                )

        # Match "from <date1> to <date2>"
        from_date_match = re.search(
            rf"\bfrom\s+({cls.MONTH_NAMES}\s+\d{{1,2}}(?:,\s*\d{{4}})?|\d{{1,2}}(?:st|nd|rd|th)?\s+{cls.MONTH_NAMES}(?:\s+\d{{4}})?|\d{{4}}-\d{{2}}-\d{{2}})\s+to\s+({cls.MONTH_NAMES}\s+\d{{1,2}}(?:,\s*\d{{4}})?|\d{{1,2}}(?:st|nd|rd|th)?\s+{cls.MONTH_NAMES}(?:\s+\d{{4}})?|\d{{4}}-\d{{2}}-\d{{2}})\b",
            text_lower,
            re.IGNORECASE,
        )
        if from_date_match and not between_date_match:
            d1_str, d2_str = from_date_match.group(1), from_date_match.group(2)
            t1, t2 = cls._parse_date_pair(d1_str, d2_str, now.year)
            if t1 and t2:
                results.append(
                    TemporalConstraint(
                        start_time=t1,
                        end_time=t2,
                        raw_text=from_date_match.group(0),
                        timezone=case_timezone,
                        precision="DAY",
                    )
                )

        # ------------------------------------------------------------------ #
        # 3. Time Ranges: "between 10 PM and midnight", "from 14:00 to 18:00"#
        # ------------------------------------------------------------------ #

        time_range_match = re.search(
            r"\b(?:between|from)\s+(\d{1,2}(?::\d{2})?\s*(?:am|pm)?|\d{1,2}:\d{2}|midnight|noon)\s+(?:and|to)\s+(\d{1,2}(?::\d{2})?\s*(?:am|pm)?|\d{1,2}:\d{2}|midnight|noon)\b",
            text_lower,
            re.IGNORECASE,
        )
        if time_range_match:
            tm1_str, tm2_str = time_range_match.group(1), time_range_match.group(2)
            st_time = cls._parse_time_str(tm1_str)
            end_time = cls._parse_time_str(tm2_str)
            if st_time and end_time:
                # Attach to current date or relative context
                base_date = results[0].start_time.date() if results and results[0].start_time else now.date()
                st_dt = datetime.combine(base_date, st_time, tzinfo=timezone.utc)
                end_dt = datetime.combine(base_date, end_time, tzinfo=timezone.utc)
                if end_dt <= st_dt:
                    end_dt += timedelta(days=1)
                
                prec = "MINUTE" if (":" in tm1_str or ":" in tm2_str) else "HOUR"
                results.append(
                    TemporalConstraint(
                        start_time=st_dt,
                        end_time=end_dt,
                        raw_text=time_range_match.group(0),
                        timezone=case_timezone,
                        precision=prec,
                    )
                )

        # ------------------------------------------------------------------ #
        # 4. Single Dates: "on September 15", "on 2026-09-30"                #
        # ------------------------------------------------------------------ #

        if not between_date_match and not from_date_match:
            single_date_match = re.search(
                rf"\b(?:on|dated?)\s+({cls.MONTH_NAMES}\s+\d{{1,2}}(?:,\s*\d{{4}})?|\d{{1,2}}(?:st|nd|rd|th)?\s+{cls.MONTH_NAMES}(?:\s+\d{{4}})?|\d{{4}}-\d{{2}}-\d{{2}})\b",
                text_lower,
                re.IGNORECASE,
            )
            if single_date_match:
                d_str = single_date_match.group(1)
                try:
                    dt = date_parser.parse(d_str, default=datetime(now.year, 1, 1))
                    start = datetime.combine(dt.date(), time.min, tzinfo=timezone.utc)
                    end = datetime.combine(dt.date(), time.max, tzinfo=timezone.utc)
                    results.append(
                        TemporalConstraint(
                            start_time=start,
                            end_time=end,
                            raw_text=single_date_match.group(0),
                            timezone=case_timezone,
                            precision="DAY",
                        )
                    )
                except Exception:
                    pass

        # ------------------------------------------------------------------ #
        # 5. Boundary expressions: "after 8 PM", "before September 10"       #
        # ------------------------------------------------------------------ #

        after_match = re.search(
            rf"\b(?:after|since)\s+({cls.MONTH_NAMES}\s+\d{{1,2}}|\d{{1,2}}(?::\d{{2}})?\s*(?:am|pm)?|\d{{4}}-\d{{2}}-\d{{2}})\b",
            text_lower,
            re.IGNORECASE,
        )
        if after_match and not results:
            target_str = after_match.group(1)
            t_val = cls._parse_time_str(target_str)
            if t_val:
                st_dt = datetime.combine(now.date(), t_val, tzinfo=timezone.utc)
                prec = "MINUTE" if ":" in target_str else "HOUR"
                results.append(
                    TemporalConstraint(
                        start_time=st_dt,
                        end_time=None,
                        raw_text=after_match.group(0),
                        timezone=case_timezone,
                        precision=prec,
                    )
                )
            else:
                try:
                    dt = date_parser.parse(target_str, default=datetime(now.year, 1, 1))
                    st_dt = datetime.combine(dt.date(), time.min, tzinfo=timezone.utc)
                    results.append(
                        TemporalConstraint(
                            start_time=st_dt,
                            end_time=None,
                            raw_text=after_match.group(0),
                            timezone=case_timezone,
                            precision="DAY",
                        )
                    )
                except Exception:
                    pass

        before_match = re.search(
            rf"\b(?:before|until)\s+({cls.MONTH_NAMES}\s+\d{{1,2}}|\d{{1,2}}(?::\d{{2}})?\s*(?:am|pm)?|\d{{4}}-\d{{2}}-\d{{2}})\b",
            text_lower,
            re.IGNORECASE,
        )
        if before_match and not results:
            target_str = before_match.group(1)
            t_val = cls._parse_time_str(target_str)
            # Check if target_str is a date month name
            is_date_month = any(m in target_str.lower() for m in ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"])
            if t_val and not is_date_month:
                end_dt = datetime.combine(now.date(), t_val, tzinfo=timezone.utc)
                prec = "MINUTE" if ":" in target_str else "HOUR"
                results.append(
                    TemporalConstraint(
                        start_time=None,
                        end_time=end_dt,
                        raw_text=before_match.group(0),
                        timezone=case_timezone,
                        precision=prec,
                    )
                )
            else:
                try:
                    dt = date_parser.parse(target_str, default=datetime(now.year, 1, 1))
                    end_dt = datetime.combine(dt.date(), time.max, tzinfo=timezone.utc)
                    results.append(
                        TemporalConstraint(
                            start_time=None,
                            end_time=end_dt,
                            raw_text=before_match.group(0),
                            timezone=case_timezone,
                            precision="DAY",
                        )
                    )
                except Exception:
                    pass

        return results

    @classmethod
    def _parse_date_pair(cls, d1_str: str, d2_str: str, default_year: int) -> Tuple[Optional[datetime], Optional[datetime]]:
        """Parses two date strings into start and end bounds."""
        try:
            dt1 = date_parser.parse(d1_str, default=datetime(default_year, 1, 1))
            dt2 = date_parser.parse(d2_str, default=datetime(default_year, 1, 1))
            st = datetime.combine(dt1.date(), time.min, tzinfo=timezone.utc)
            end = datetime.combine(dt2.date(), time.max, tzinfo=timezone.utc)
            return st, end
        except Exception:
            return None, None

    @classmethod
    def _parse_time_str(cls, t_str: str) -> Optional[time]:
        """Parses colloquial time expressions like '10 PM', 'midnight', '14:30'."""
        clean = t_str.strip().lower()
        if clean == "midnight":
            return time(0, 0, 0)
        if clean == "noon":
            return time(12, 0, 0)
        try:
            dt = date_parser.parse(clean)
            return dt.time()
        except Exception:
            return None

    # Instance & alias methods
    def extract_temporal_constraints(
        self,
        text: str,
        reference_time: Optional[datetime] = None,
        case_timezone: str = "UTC"
    ) -> List[TemporalConstraint]:
        """Instance alias for parse_temporal_expressions."""
        return self.parse_temporal_expressions(text, reference_time, case_timezone)

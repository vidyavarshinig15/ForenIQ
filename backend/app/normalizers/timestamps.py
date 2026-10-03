from dataclasses import dataclass
from datetime import datetime, timezone
import re
from typing import Any, Optional, Tuple

from backend.app.models.enums import TimestampPrecision, TimestampStatus


@dataclass
class TimestampResult:
    """Standardized result of timestamp parsing and precision extraction."""
    normalized_utc: Optional[datetime]
    precision: TimestampPrecision
    status: TimestampStatus
    original_timestamp: Optional[str]
    original_timezone: Optional[str]


# Pre-compiled Regex Patterns for deterministic precision matching
ISO_MS_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}\.\d+(?:Z|[+-]\d{2}:?\d{2})?$")
ISO_SEC_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}(?:Z|[+-]\d{2}:?\d{2})?$")
ISO_MIN_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}(?:Z|[+-]\d{2}:?\d{2})?$")
ISO_HOUR_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}[T ]\d{2}$")
DATE_DAY_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}$")
DATE_MONTH_PATTERN = re.compile(r"^\d{4}-\d{2}$")
DATE_YEAR_PATTERN = re.compile(r"^\d{4}$")

TIMEZONE_EXTRACT_PATTERN = re.compile(r"(Z|[+-]\d{2}:?\d{2}|[A-Z]{3,4})$")


def _detect_precision(raw_str: str) -> TimestampPrecision:
    """Identify precision level based on raw lexical pattern."""
    s = raw_str.strip()
    if ISO_MS_PATTERN.match(s):
        return TimestampPrecision.MILLISECOND
    if ISO_SEC_PATTERN.match(s):
        return TimestampPrecision.SECOND
    if ISO_MIN_PATTERN.match(s):
        return TimestampPrecision.MINUTE
    if ISO_HOUR_PATTERN.match(s):
        return TimestampPrecision.HOUR
    if DATE_DAY_PATTERN.match(s):
        return TimestampPrecision.DAY
    if DATE_MONTH_PATTERN.match(s):
        return TimestampPrecision.MONTH
    if DATE_YEAR_PATTERN.match(s):
        return TimestampPrecision.YEAR
    return TimestampPrecision.UNKNOWN


def _extract_timezone_string(raw_str: str) -> Optional[str]:
    """Extract explicit timezone suffix if present."""
    match = TIMEZONE_EXTRACT_PATTERN.search(raw_str.strip())
    if match:
        tz = match.group(1)
        return "UTC" if tz == "Z" else tz
    return None


def normalize_timestamp(raw_val: Any) -> TimestampResult:
    """
    Safely normalizes raw timestamp values from UFDR evidence into a UTC datetime
    and exact precision indicator without inventing missing data.
    """
    if raw_val is None:
        return TimestampResult(
            normalized_utc=None,
            precision=TimestampPrecision.UNKNOWN,
            status=TimestampStatus.UNKNOWN,
            original_timestamp=None,
            original_timezone=None,
        )

    orig_str = str(raw_val).strip()
    if not orig_str or orig_str.lower() in ("null", "none", "unknown", "n/a", "0", "0000-00-00"):
        return TimestampResult(
            normalized_utc=None,
            precision=TimestampPrecision.UNKNOWN,
            status=TimestampStatus.UNKNOWN,
            original_timestamp=orig_str if orig_str else None,
            original_timezone=None,
        )

    # 0. Check 4-digit calendar year (e.g. "2026")
    if DATE_YEAR_PATTERN.match(orig_str):
        year_num = int(orig_str)
        if 1900 <= year_num <= 2100:
            return TimestampResult(
                normalized_utc=datetime(year_num, 1, 1, tzinfo=timezone.utc),
                precision=TimestampPrecision.YEAR,
                status=TimestampStatus.VALID,
                original_timestamp=orig_str,
                original_timezone=None,
            )

    # 1. Numeric Unix timestamp check (integer or float)
    if isinstance(raw_val, (int, float)) or (re.match(r"^-?\d+(\.\d+)?$", orig_str)):
        try:
            num = float(raw_val)
            # Differentiate epoch seconds vs milliseconds vs microseconds
            if num > 1e14:  # Microseconds
                dt = datetime.fromtimestamp(num / 1e6, tz=timezone.utc)
                precision = TimestampPrecision.MILLISECOND
            elif num > 1e11:  # Milliseconds
                dt = datetime.fromtimestamp(num / 1e3, tz=timezone.utc)
                precision = TimestampPrecision.MILLISECOND
            elif num > 0:  # Seconds
                dt = datetime.fromtimestamp(num, tz=timezone.utc)
                precision = TimestampPrecision.MILLISECOND if "." in orig_str else TimestampPrecision.SECOND
            else:
                return TimestampResult(
                    normalized_utc=None,
                    precision=TimestampPrecision.UNKNOWN,
                    status=TimestampStatus.INVALID,
                    original_timestamp=orig_str,
                    original_timezone=None,
                )

            return TimestampResult(
                normalized_utc=dt,
                precision=precision,
                status=TimestampStatus.VALID,
                original_timestamp=orig_str,
                original_timezone="UTC",
            )
        except (ValueError, OverflowError, OSError):
            return TimestampResult(
                normalized_utc=None,
                precision=TimestampPrecision.UNKNOWN,
                status=TimestampStatus.INVALID,
                original_timestamp=orig_str,
                original_timezone=None,
            )

    # 2. String timestamp parsing
    orig_tz = _extract_timezone_string(orig_str)
    precision = _detect_precision(orig_str)

    # Handle partial dates: Year, Month, Day
    if precision == TimestampPrecision.YEAR:
        try:
            year = int(orig_str)
            if 1970 <= year <= 2100:
                dt = datetime(year, 1, 1, tzinfo=timezone.utc)
                return TimestampResult(
                    normalized_utc=dt,
                    precision=TimestampPrecision.YEAR,
                    status=TimestampStatus.VALID,
                    original_timestamp=orig_str,
                    original_timezone=orig_tz or "UNKNOWN",
                )
        except ValueError:
            pass

    if precision == TimestampPrecision.MONTH:
        try:
            dt = datetime.strptime(orig_str, "%Y-%m").replace(tzinfo=timezone.utc)
            return TimestampResult(
                normalized_utc=dt,
                precision=TimestampPrecision.MONTH,
                status=TimestampStatus.VALID,
                original_timestamp=orig_str,
                original_timezone=orig_tz or "UNKNOWN",
            )
        except ValueError:
            pass

    if precision == TimestampPrecision.DAY:
        try:
            dt = datetime.strptime(orig_str, "%Y-%m-%d").replace(tzinfo=timezone.utc)
            return TimestampResult(
                normalized_utc=dt,
                precision=TimestampPrecision.DAY,
                status=TimestampStatus.VALID,
                original_timestamp=orig_str,
                original_timezone=orig_tz or "UNKNOWN",
            )
        except ValueError:
            pass

    # Try ISO 8601 parsing via fromisoformat
    try:
        # Normalize 'Z' to '+00:00' for fromisoformat
        clean_iso = orig_str.replace("Z", "+00:00")
        dt = datetime.fromisoformat(clean_iso)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        else:
            dt = dt.astimezone(timezone.utc)

        if precision == TimestampPrecision.UNKNOWN:
            precision = TimestampPrecision.MILLISECOND if dt.microsecond else TimestampPrecision.SECOND

        return TimestampResult(
            normalized_utc=dt,
            precision=precision,
            status=TimestampStatus.VALID,
            original_timestamp=orig_str,
            original_timezone=orig_tz or "UNKNOWN",
        )
    except (ValueError, TypeError):
        pass

    # Fallback to common forensic formats
    standard_formats = [
        ("%Y-%m-%d %H:%M:%S", TimestampPrecision.SECOND),
        ("%Y/%m/%d %H:%M:%S", TimestampPrecision.SECOND),
        ("%d/%m/%Y %H:%M:%S", TimestampPrecision.SECOND),
        ("%m/%d/%Y %H:%M:%S", TimestampPrecision.SECOND),
        ("%Y-%m-%d %H:%M:%S.%f", TimestampPrecision.MILLISECOND),
        ("%d-%m-%Y %H:%M:%S", TimestampPrecision.SECOND),
    ]

    for fmt, prec in standard_formats:
        try:
            parsed = datetime.strptime(orig_str, fmt)
            dt = parsed.replace(tzinfo=timezone.utc)
            return TimestampResult(
                normalized_utc=dt,
                precision=prec,
                status=TimestampStatus.VALID,
                original_timestamp=orig_str,
                original_timezone=orig_tz or "UNKNOWN",
            )
        except (ValueError, TypeError):
            continue

    # Unparseable / Malformed
    return TimestampResult(
        normalized_utc=None,
        precision=TimestampPrecision.UNKNOWN,
        status=TimestampStatus.INVALID,
        original_timestamp=orig_str,
        original_timezone=orig_tz,
    )

import re
from typing import Any, Dict, List, Optional, Tuple

from backend.app.models.enums import EntityType


# Canonical application mappings (package identifiers / variants -> standardized names)
KNOWN_APPLICATION_MAP = {
    # WhatsApp
    "com.whatsapp": "WhatsApp",
    "com.whatsapp.w4b": "WhatsApp Business",
    "whatsapp": "WhatsApp",
    "whatsapp messenger": "WhatsApp",
    # Telegram
    "org.telegram.messenger": "Telegram",
    "org.telegram.plus": "Telegram",
    "telegram": "Telegram",
    # Signal
    "org.thoughtcrime.securesms": "Signal",
    "signal": "Signal",
    # Instagram
    "com.instagram.android": "Instagram",
    "instagram": "Instagram",
    # Chrome
    "com.android.chrome": "Chrome",
    "google chrome": "Chrome",
    "chrome": "Chrome",
    # Safari
    "safari": "Safari",
    "mobile safari": "Safari",
    "com.apple.mobilesafari": "Safari",
    # Firefox
    "org.mozilla.firefox": "Firefox",
    "firefox": "Firefox",
    # SMS / MMS / Stock
    "com.google.android.apps.messaging": "Messages",
    "com.samsung.android.messaging": "Messages",
    "com.apple.mobilesms": "iMessage",
    "sms": "SMS",
    "mms": "MMS",
    "imessage": "iMessage",
    # Calls / Dialer
    "com.google.android.dialer": "Phone",
    "com.samsung.android.dialer": "Phone",
    "com.apple.mobilephone": "Phone",
    "phone": "Phone",
}


def normalize_phone_number(raw_phone: Any) -> Tuple[Optional[str], Optional[str]]:
    """
    Normalizes phone numbers safely.
    Returns (normalized_phone, original_phone).
    Preserves leading '+' for international numbers, removes formatting artifacts (spaces, dashes, parens).
    """
    if raw_phone is None:
        return None, None

    orig = str(raw_phone).strip()
    if not orig or orig.lower() in ("unknown", "null", "none", "private", "blocked", "restricted"):
        return None, orig if orig else None

    # Check for international prefix '+'
    has_plus = orig.startswith("+")
    # Strip all non-digit characters
    digits_only = re.sub(r"\D", "", orig)

    if not digits_only:
        return None, orig

    # If it had a '+', restore it
    normalized = f"+{digits_only}" if has_plus else digits_only
    return normalized, orig


def normalize_email(raw_email: Any) -> Tuple[Optional[str], Optional[str]]:
    """
    Normalizes email addresses safely.
    Returns (normalized_email, original_email).
    """
    if raw_email is None:
        return None, None

    orig = str(raw_email).strip()
    if not orig or "@" not in orig:
        return None, orig if orig else None

    clean = orig.lower()
    # Simple RFC 5322 sanity check
    if re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", clean):
        return clean, orig

    return None, orig


def normalize_application_name(raw_app: Any) -> Tuple[Optional[str], Optional[str]]:
    """
    Maps known package identifiers or raw app strings to canonical application names.
    Returns (canonical_application, original_application).
    """
    if raw_app is None:
        return None, None

    orig = str(raw_app).strip()
    if not orig:
        return None, None

    lower_key = orig.lower()
    canonical = KNOWN_APPLICATION_MAP.get(lower_key)
    if canonical:
        return canonical, orig

    # If not in known canonical mapping, preserve original without unsupported alterations
    return orig, orig


def create_entity_ref(
    entity_type: EntityType,
    raw_value: Any,
    role: str,
    normalized_value: Optional[str] = None,
) -> Dict[str, Any]:
    """Helper creating a consistent, structured entity reference object."""
    return {
        "entity_type": entity_type.value,
        "entity_value": str(raw_value).strip(),
        "normalized_value": normalized_value,
        "role": role,
    }

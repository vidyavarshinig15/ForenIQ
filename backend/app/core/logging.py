import logging
import re
import sys
from datetime import datetime, timezone
from typing import Any, Dict


# Patterns to redact from logs
SENSITIVE_PATTERNS = [
    (re.compile(r'(password|secret|token|api[_-]?key|jwt)[\'"]?\s*[:=]\s*[\'"]?([^\s,\'";}]+)', re.IGNORECASE), r'\1: "[REDACTED]"'),
    (re.compile(r'Bearer\s+[A-Za-z0-9\-_=]+\.[A-Za-z0-9\-_=]+\.?[A-Za-z0-9\-_=]*', re.IGNORECASE), 'Bearer [REDACTED]'),
]


class ForensicLogFormatter(logging.Formatter):
    """
    Standardized structured formatter for forensic application logs.
    Ensures timestamp, severity, module name, and sanitized messages.
    """

    def format(self, record: logging.LogRecord) -> str:
        timestamp = datetime.now(timezone.utc).isoformat()
        original_msg = super().format(record)

        # Sanitize sensitive values
        sanitized_msg = original_msg
        for pattern, replacement in SENSITIVE_PATTERNS:
            sanitized_msg = pattern.sub(replacement, sanitized_msg)

        return f"[{timestamp}] [{record.levelname:<7}] [{record.name}] {sanitized_msg}"


def setup_logging(log_level: str = "INFO") -> None:
    """
    Configures root and application loggers with structured formatting and level.
    """
    level = getattr(logging, log_level.upper(), logging.INFO)

    root_logger = logging.getLogger()
    root_logger.setLevel(level)

    # Remove existing handlers to avoid duplicates
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(level)
    console_handler.setFormatter(ForensicLogFormatter("%(message)s"))

    root_logger.addHandler(console_handler)

    # Silence overly verbose external loggers
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    """
    Returns a logger instance namespaced to the given module.
    """
    return logging.getLogger(name)

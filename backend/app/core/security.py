import time
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional, Tuple
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError
import jwt
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from backend.app.core.config import get_settings
from backend.app.core.errors import ForensicAppException

settings = get_settings()

# Initialize Argon2id password hasher with robust parameters
_ph = PasswordHasher(
    time_cost=3,
    memory_cost=65536,  # 64 MB
    parallelism=2,
    hash_len=32,
    salt_len=16,
)


def hash_password(password: str) -> str:
    """Hash a plaintext password using Argon2id."""
    return _ph.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a plaintext password against an Argon2id hash."""
    try:
        return _ph.verify(hashed_password, plain_password)
    except (VerifyMismatchError, Exception):
        return False


def create_access_token(subject: str, role: str, expires_delta: Optional[timedelta] = None) -> str:
    """
    Creates a cryptographically signed JWT access token.
    Payload contains subject (user UUID), role, issuance, and expiration timestamps.
    """
    now = datetime.now(timezone.utc)
    if expires_delta:
        expire = now + expires_delta
    else:
        expire = now + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)

    to_encode: Dict[str, Any] = {
        "sub": str(subject),
        "role": str(role),
        "iat": int(now.timestamp()),
        "exp": int(expire.timestamp()),
        "iss": settings.APP_NAME,
    }

    return jwt.encode(to_encode, settings.JWT_SECRET, algorithm=settings.ALGORITHM)


def decode_access_token(token: str) -> Dict[str, Any]:
    """
    Decodes and validates a JWT access token.
    Raises ForensicAppException if the token is expired, invalid, or malformed.
    """
    try:
        payload = jwt.decode(
            token,
            settings.JWT_SECRET,
            algorithms=[settings.ALGORITHM],
            issuer=settings.APP_NAME,
        )
        return payload
    except jwt.ExpiredSignatureError:
        raise ForensicAppException(
            message="Authentication token has expired. Please log in again.",
            code="TOKEN_EXPIRED",
            status_code=401,
        )
    except jwt.PyJWTError:
        raise ForensicAppException(
            message="Invalid authentication credentials.",
            code="TOKEN_INVALID",
            status_code=401,
        )


class LoginRateLimiter:
    """
    In-memory sliding window rate-limiter for failed authentication attempts.
    Mitigates brute-force attacks by throttling accounts/IPs exceeding threshold.
    """
    def __init__(self, max_attempts: int = 5, lockout_seconds: int = 900):
        self.max_attempts = max_attempts
        self.lockout_seconds = lockout_seconds
        # key: email_or_ip -> (failure_count, lockout_until_timestamp)
        self._records: Dict[str, Tuple[int, float]] = {}

    def is_locked(self, key: str) -> bool:
        normalized_key = key.lower().strip()
        record = self._records.get(normalized_key)
        if not record:
            return False
        count, lockout_until = record
        if time.time() < lockout_until:
            return True
        if lockout_until > 0:
            # Lockout expired, reset
            del self._records[normalized_key]
        return False

    def record_failure(self, key: str) -> None:
        normalized_key = key.lower().strip()
        now = time.time()
        record = self._records.get(normalized_key)
        if not record:
            self._records[normalized_key] = (1, 0.0)
            return

        count, lockout_until = record
        if now < lockout_until:
            return

        new_count = count + 1
        if new_count >= self.max_attempts:
            self._records[normalized_key] = (new_count, now + self.lockout_seconds)
        else:
            self._records[normalized_key] = (new_count, 0.0)

    def record_success(self, key: str) -> None:
        normalized_key = key.lower().strip()
        if normalized_key in self._records:
            del self._records[normalized_key]


login_rate_limiter = LoginRateLimiter(
    max_attempts=settings.MAX_FAILED_LOGIN_ATTEMPTS,
    lockout_seconds=settings.LOCKOUT_DURATION_MINUTES * 60,
)


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """
    Applies hardened forensic HTTP security headers to all incoming responses.
    """

    async def dispatch(self, request: Request, call_next) -> Response:
        response: Response = await call_next(request)

        # Enforce MIME type sniffing protection
        response.headers["X-Content-Type-Options"] = "nosniff"

        # Prevent clickjacking / frame embedding
        response.headers["X-Frame-Options"] = "DENY"

        # Disable browser caching of sensitive forensic API responses
        if request.url.path.startswith("/api/"):
            response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
            response.headers["Pragma"] = "no-cache"

        # Strict Referrer policy
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"

        # Standard Content Security Policy for API
        response.headers["Content-Security-Policy"] = "default-src 'none'; frame-ancestors 'none'"

        return response

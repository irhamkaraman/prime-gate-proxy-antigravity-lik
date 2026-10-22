"""
Security middleware package for Prime Gate.
Protects against DNS rebinding, cross-origin attacks on localhost,
CSRF, clickjacking, and MIME sniffing.
"""

from .middleware import (
    HostValidationMiddleware,
    StrictOriginMiddleware,
    CSRFMiddleware,
    SecurityHeadersMiddleware,
)
from .rate_limiter import KeyRateLimiter

__all__ = [
    "HostValidationMiddleware",
    "StrictOriginMiddleware",
    "CSRFMiddleware",
    "SecurityHeadersMiddleware",
    "KeyRateLimiter",
]

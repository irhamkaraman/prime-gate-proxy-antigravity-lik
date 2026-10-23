import os
import re
import uuid
from urllib.parse import urlparse
from typing import Set, Optional
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response, JSONResponse

from ..crypto.auth_manager import AuthManager, COOKIE_SESSION_NAME, HEADER_CSRF_NAME

DEFAULT_ALLOWED_HOSTS: Set[str] = {
    "localhost",
    "127.0.0.1",
    "::1",
    "0.0.0.0",
    "testserver",
}


def _get_allowed_hosts() -> Set[str]:
    hosts = set(DEFAULT_ALLOWED_HOSTS)
    env_hosts = os.getenv("ALLOWED_HOSTS", "")
    if env_hosts:
        for h in env_hosts.split(","):
            cleaned = h.strip().lower()
            if cleaned:
                hosts.add(cleaned)
    return hosts


def _normalize_host(host_header: Optional[str]) -> str:
    if not host_header:
        return ""
    # Strip port number if present (e.g., "localhost:52111" -> "localhost")
    # Handle IPv6 bracket format [::1]:52111
    if host_header.startswith("["):
        end_bracket = host_header.find("]")
        if end_bracket != -1:
            return host_header[1:end_bracket].lower()
    return host_header.split(":")[0].strip().lower()


class HostValidationMiddleware(BaseHTTPMiddleware):
    """
    Mitigates DNS Rebinding attacks by validating the Host header against
    a strict local allowlist. Rejects requests from malicious domain names (e.g. attacker.com)
    that resolve to 127.0.0.1.
    """

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        host_header = request.headers.get("host", "")
        normalized = _normalize_host(host_header)
        allowed = _get_allowed_hosts()

        if not normalized or normalized not in allowed:
            return JSONResponse(
                status_code=403,
                content={
                    "error": {
                        "message": f"Forbidden: Host '{host_header}' is not allowed (DNS Rebinding Mitigation).",
                        "type": "security_error",
                        "code": "invalid_host"
                    }
                }
            )
        return await call_next(request)


class StrictOriginMiddleware(BaseHTTPMiddleware):
    """
    Prevents unauthorized cross-origin requests from external web pages targeting localhost.
    Validates the Origin header for state-changing HTTP requests.
    """

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        method = request.method.upper()
        # Only inspect state-changing requests directed at the internal API
        if method in {"POST", "PUT", "DELETE", "PATCH"} and request.url.path.startswith("/api/"):
            origin = request.headers.get("origin")
            if origin:
                parsed = urlparse(origin)
                origin_host = (parsed.hostname or "").lower()
                allowed = _get_allowed_hosts()
                if origin_host not in allowed:
                    return JSONResponse(
                        status_code=403,
                        content={
                            "error": {
                                "message": f"Forbidden: Origin '{origin}' is not authorized to perform mutations.",
                                "type": "security_error",
                                "code": "invalid_origin"
                            }
                        }
                    )
        return await call_next(request)


class CSRFMiddleware(BaseHTTPMiddleware):
    """
    Enforces double-submit CSRF token validation for session-authenticated
    state-changing requests on /api/* endpoints.
    API key requests (Bearer / x-api-key) and the login endpoint are exempt.
    """

    EXEMPT_PATHS = {
        "/api/auth/session",
        "/api/auth/session/status",
        "/api/auth/session/logout",
        "/api/auth/session/local-login"
    }

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        method = request.method.upper()
        path = request.url.path

        if method in {"POST", "PUT", "DELETE", "PATCH"} and path.startswith("/api/"):
            if path in self.EXEMPT_PATHS:
                return await call_next(request)

            # Check if this request is using an API key directly
            auth_header = request.headers.get("authorization", "")
            api_key_header = request.headers.get("x-api-key", "")
            if auth_header.lower().startswith("bearer ") or api_key_header:
                # API key authenticated requests are stateless and exempt from browser CSRF
                return await call_next(request)

            # Check session cookie
            session_id = request.cookies.get(COOKIE_SESSION_NAME)
            if session_id:
                csrf_header = request.headers.get(HEADER_CSRF_NAME) or request.headers.get("x-csrf-token")
                if not AuthManager.validate_csrf(session_id, csrf_header):
                    return JSONResponse(
                        status_code=403,
                        content={
                            "error": {
                                "message": "Forbidden: Missing or invalid CSRF token.",
                                "type": "security_error",
                                "code": "csrf_validation_failed"
                            }
                        }
                    )

        return await call_next(request)


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """
    Injects defensive HTTP response headers:
    - Content-Security-Policy (CSP)
    - X-Content-Type-Options: nosniff
    - X-Frame-Options: DENY (anti-clickjacking)
    - Referrer-Policy: strict-origin-when-cross-origin
    """

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline'; "
            "style-src 'self' 'unsafe-inline'; "
            "img-src 'self' data: https:; "
            "connect-src 'self' ws: wss:; "
            "frame-ancestors 'none';"
        )
        return response


class RequestTracingMiddleware(BaseHTTPMiddleware):
    """
    Propagates or generates X-Request-ID for end-to-end distributed tracing.
    Attaches sanitized request_id to request.state and every outgoing response header.
    """

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        raw_id = request.headers.get("x-request-id") or request.headers.get("X-Request-ID")
        if raw_id:
            # Sanitize to alphanumeric + dashes/underscores, max length 64
            req_id = re.sub(r"[^a-zA-Z0-9_\-]", "", raw_id)[:64]
            if not req_id:
                req_id = uuid.uuid4().hex
        else:
            req_id = uuid.uuid4().hex

        request.state.request_id = req_id
        response = await call_next(request)
        response.headers["X-Request-ID"] = req_id
        return response

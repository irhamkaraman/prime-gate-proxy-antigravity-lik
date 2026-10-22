import re
import logging
from typing import Any, Dict, List, Union

REDACTION_PATTERNS: List[Tuple_pattern := re.compile] = [
    # Google OAuth 2.0 Access Token
    (re.compile(r"ya29\.[a-zA-Z0-9_\-]+"), "ya29.[REDACTED_OAUTH_TOKEN]"),
    # Google OAuth 2.0 Refresh Token
    (re.compile(r"1//[a-zA-Z0-9_\-]+"), "1//[REDACTED_REFRESH_TOKEN]"),
    # Google Client Secret
    (re.compile(r"GOCSPX-[a-zA-Z0-9_\-]+"), "GOCSPX-[REDACTED_SECRET]"),
    # Prime Gate API Keys
    (re.compile(r"pg-live-[a-zA-Z0-9_\-]{16,}"), "pg-live-[REDACTED_API_KEY]"),
    # Standard OpenAI / Anthropic format keys
    (re.compile(r"sk-[a-zA-Z0-9_\-]{20,}"), "sk-[REDACTED_API_KEY]"),
    # Bearer header in curl, raw text, or logs
    (re.compile(r"(?i)(bearer\s+)([a-zA-Z0-9_\-\.]{15,})"), r"\1[REDACTED_BEARER]"),
    # x-api-key header / string
    (re.compile(r"(?i)(x-api-key\s*[:=]\s*['\"]?)([a-zA-Z0-9_\-\.]{12,})(['\"]?)"), r"\1[REDACTED_API_KEY]\3"),
    # Cookie pg_session / auth session
    (re.compile(r"(pg_session=)([a-zA-Z0-9_\-]+)"), r"\1[REDACTED_SESSION]"),
    (re.compile(r"(pg_csrf=)([a-zA-Z0-9_\-]+)"), r"\1[REDACTED_CSRF]"),
]

# Email masking regex
EMAIL_PATTERN = re.compile(r"([a-zA-Z0-9_.+-])[a-zA-Z0-9_.+-]*@([a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+)")


class Redactor:
    """Central engine for scrubbing sensitive credentials from strings, dicts, and exceptions."""

    @staticmethod
    def mask_string(text: str, mask_emails: bool = False) -> str:
        if not text or not isinstance(text, str):
            return text
        result = text
        for pattern, replacement in REDACTION_PATTERNS:
            result = pattern.sub(replacement, result)

        if mask_emails:
            result = EMAIL_PATTERN.sub(r"\1***@\2", result)
        return result

    @staticmethod
    def mask_object(obj: Any, mask_emails: bool = False) -> Any:
        """Recursively traverses dictionaries, lists, and primitives to redact sensitive fields."""
        if isinstance(obj, str):
            return Redactor.mask_string(obj, mask_emails=mask_emails)
        elif isinstance(obj, dict):
            masked_dict = {}
            for k, v in obj.items():
                lower_k = str(k).lower()
                if any(sec in lower_k for sec in ["token", "secret", "password", "refreshtoken", "key_hash", "salt", "authorization"]):
                    if isinstance(v, str) and len(v) > 0:
                        masked_dict[k] = "[REDACTED]"
                    else:
                        masked_dict[k] = Redactor.mask_object(v, mask_emails=mask_emails)
                else:
                    masked_dict[k] = Redactor.mask_object(v, mask_emails=mask_emails)
            return masked_dict
        elif isinstance(obj, (list, tuple)):
            masked_list = [Redactor.mask_object(item, mask_emails=mask_emails) for item in obj]
            return type(obj)(masked_list)
        return obj


class RedactingLogFilter(logging.Filter):
    """Logging filter that scrubs sensitive credentials from every log record message."""

    def filter(self, record: logging.LogRecord) -> bool:
        if isinstance(record.msg, str):
            record.msg = Redactor.mask_string(record.msg)
        if record.args:
            if isinstance(record.args, dict):
                record.args = Redactor.mask_object(record.args)
            elif isinstance(record.args, tuple):
                record.args = tuple(Redactor.mask_object(a) for a in record.args)
        return True


class RedactingFormatter(logging.Formatter):
    """Logging formatter that ensures formatted output is strictly redacted."""

    def format(self, record: logging.LogRecord) -> str:
        formatted = super().format(record)
        return Redactor.mask_string(formatted)


class RedactingJsonFormatter(logging.Formatter):
    """
    JSON logging formatter for structured observability.
    Outputs single-line JSON with ISO 8601 timestamp, level, logger name, request_id,
    and message, scrubbed of any secret credentials.
    """

    def format(self, record: logging.LogRecord) -> str:
        import json
        import time

        data = {
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(record.created)),
            "level": record.levelname,
            "logger": record.name,
            "message": Redactor.mask_string(record.getMessage())
        }
        if hasattr(record, "request_id"):
            data["request_id"] = record.request_id
        if record.exc_info:
            data["exception"] = Redactor.mask_string(self.formatException(record.exc_info))
        return json.dumps(data)

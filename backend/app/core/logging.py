"""Minimal application logging.

- Writes to standard output (the process manager or terminal collects it).
- Uses UTC timestamps in ISO 8601 style.
- Redacts values that follow sensitive keys (password, token, secret,
  api key, authorization) so they do not reach the logs by accident.

This is a safety net, not a licence to log secrets: code must still
avoid passing credentials to the logger in the first place.
"""

import logging
import re
import sys
import time

_HANDLER_NAME = "autopay-console"
_REDACTED = "***REDACTED***"

_SENSITIVE_PATTERN = re.compile(
    r"(?i)\b(password|passwd|secret|token|api[_-]?key|authorization)\b"
    r"(\s*[=:]\s*)((?:bearer|basic)\s+)?(\S+)"
)


def _redact(match: re.Match) -> str:
    return f"{match.group(1)}{match.group(2)}{_REDACTED}"


class RedactSecretsFilter(logging.Filter):
    """Mask values that follow sensitive keys in log messages."""

    def filter(self, record: logging.LogRecord) -> bool:
        message = record.getMessage()
        redacted = _SENSITIVE_PATTERN.sub(_redact, message)
        if redacted != message:
            record.msg = redacted
            record.args = None
        return True


def configure_logging(level: str = "INFO") -> None:
    """Configure root logging once; safe to call repeatedly."""
    root = logging.getLogger()

    # Remove only the handler installed by this function, so repeated
    # calls (tests, reloads) never produce duplicate log lines.
    for handler in list(root.handlers):
        if handler.get_name() == _HANDLER_NAME:
            root.removeHandler(handler)

    formatter = logging.Formatter(
        fmt="%(asctime)sZ | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S",
    )
    formatter.converter = time.gmtime  # timestamps in UTC

    handler = logging.StreamHandler(sys.stdout)
    handler.set_name(_HANDLER_NAME)
    handler.setFormatter(formatter)
    handler.addFilter(RedactSecretsFilter())

    root.addHandler(handler)
    root.setLevel(level)

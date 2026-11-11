"""tos_redact — scrub secrets and identifiers from text before an AI sees it.

Shared by tos-mcp (every read tool's output) and, going forward, tos-doctor.
Pattern-based: it catches the common shapes, not every possible secret.
"""

from __future__ import annotations

import getpass
import os
import re

_RULES: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----.*?-----END [A-Z ]*PRIVATE KEY-----", re.S),
     "[REDACTED-PRIVATE-KEY]"),
    (re.compile(r"\b(gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,})"), "[REDACTED-GITHUB-TOKEN]"),
    (re.compile(r"\bsk-[A-Za-z0-9_-]{20,}"), "[REDACTED-API-KEY]"),
    (re.compile(r"\b(AKIA|ASIA)[A-Z0-9]{16}\b"), "[REDACTED-AWS-KEY]"),
    (re.compile(r"\bxox[abpors]-[A-Za-z0-9-]{10,}"), "[REDACTED-SLACK-TOKEN]"),
    (re.compile(r"\beyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}"), "[REDACTED-JWT]"),
    (re.compile(r"(?i)\btskey-[A-Za-z0-9-]+"), "[REDACTED-TAILSCALE-KEY]"),
    (re.compile(r"(?i)\b(password|passwd|secret|token|api[_-]?key|authorization)\s*[=:]\s*\S+"),
     r"\1=[REDACTED]"),
    (re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}"), "[REDACTED-EMAIL]"),
    (re.compile(r"\b([0-9A-Fa-f]{2}:){5}[0-9A-Fa-f]{2}\b"), "[REDACTED-MAC]"),
]

_IPV4 = re.compile(r"\b(\d{1,3})\.(\d{1,3})\.\d{1,3}\.\d{1,3}\b")


def _ip(m: re.Match[str]) -> str:
    a, b = int(m.group(1)), int(m.group(2))
    private = (a in (0, 10, 127) or (a == 172 and 16 <= b <= 31) or
               (a == 192 and b == 168) or (a == 100 and 64 <= b <= 127))
    return m.group(0) if private else "[REDACTED-PUBLIC-IP]"


def redact(text: str, user: str | None = None, host: str | None = None) -> str:
    """Return text with secrets, emails, MACs, public IPs, user and host name removed.

    Private and tailnet (100.64/10) addresses are kept: they matter for debugging
    and identify nothing outside your own network.
    """
    for pattern, replacement in _RULES:
        text = pattern.sub(replacement, text)
    text = _IPV4.sub(_ip, text)
    user = user if user is not None else getpass.getuser()
    host = host if host is not None else os.uname().nodename
    if user and len(user) > 2:
        text = re.sub(rf"\b{re.escape(user)}\b", "USER", text)
    if host and len(host) > 2:
        text = re.sub(rf"\b{re.escape(host)}\b", "HOST", text)
    return text

"""What Friday's settings page reads and writes. No GTK here, so it's testable.

  agent.conf      ~/.config/tegendo-os/agent.conf  (KEY=value; shared with tos-agent)
  instructions    ~/.config/tegendo-os/friday.md
  autostart       ~/.config/autostart/tos-friday.desktop (Hidden=true disables the system one)
  terminal welcome ~/.config/tegendo-os/no-welcome (present = off)
"""
from __future__ import annotations

import json
import os
import re
import shutil
import urllib.error
import urllib.request
from pathlib import Path

HOME = Path.home()
CONFIG = Path(os.environ.get("XDG_CONFIG_HOME", HOME / ".config"))
TOS_CONFIG = CONFIG / "tegendo-os"
AGENT_CONF = TOS_CONFIG / "agent.conf"
INSTRUCTIONS = TOS_CONFIG / "friday.md"
NO_WELCOME = TOS_CONFIG / "no-welcome"
AUTOSTART = CONFIG / "autostart" / "tos-friday.desktop"
AUDIT_LOG = Path(os.environ.get("XDG_STATE_HOME", HOME / ".local/state")) / "tegendo-os/friday/audit.jsonl"

BACKENDS = [("auto", "Claude, then local model"), ("claude", "Claude only"), ("ollama", "Local model only")]
CLAUDE_MODELS = [("", "Default"), ("opus", "Opus"), ("sonnet", "Sonnet"), ("haiku", "Haiku")]
KEY_RE = re.compile(r"^[A-Z_][A-Z0-9_]*$")
VALUE_RE = re.compile(r"^[A-Za-z0-9:/._@+-]*$")


def read_conf() -> dict[str, str]:
    from .backends import read_agent_conf
    return read_agent_conf()


def write_conf(updates: dict[str, str], path: Path | None = None) -> None:
    """Update KEY=value lines in agent.conf, keeping comments and other keys.
    Values are restricted (no spaces, quotes or $), since tos-agent sources the file."""
    path = path or AGENT_CONF
    for k, v in updates.items():
        if not KEY_RE.match(k) or not VALUE_RE.match(v):
            raise ValueError(f"refusing to write {k}={v!r}")
    lines = path.read_text().splitlines() if path.exists() else ["# tegendo-os agent config (edit freely)."]
    seen = set()
    for i, line in enumerate(lines):
        key = line.split("=", 1)[0].strip() if "=" in line and not line.lstrip().startswith("#") else None
        if key in updates:
            lines[i] = f"{key}='{updates[key]}'"
            seen.add(key)
    lines += [f"{k}='{v}'" for k, v in updates.items() if k not in seen]
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text("\n".join(lines) + "\n")
    tmp.chmod(0o600)
    tmp.replace(path)


def claude_status() -> str:
    path = shutil.which("claude")
    return f"Claude Code installed ({path})" if path else "Claude Code isn't installed; Friday will use the local model"


def test_ollama(url: str, model: str, timeout: float = 4.0) -> tuple[bool, str]:
    try:
        with urllib.request.urlopen(url.rstrip("/") + "/api/tags", timeout=timeout) as r:
            names = [m.get("name", "") for m in json.load(r).get("models", [])]
    except (urllib.error.URLError, OSError, ValueError) as e:
        return False, f"Can't reach {url}: {getattr(e, 'reason', e)}"
    if model and not any(n == model or n.split(":")[0] == model for n in names):
        return False, f"Connected, but {model} isn't pulled there ({len(names)} models available)"
    return True, f"Connected · {len(names)} models · {model or 'model'} ready"


def read_instructions() -> str:
    try:
        return INSTRUCTIONS.read_text()
    except OSError:
        return ""


def write_instructions(text: str) -> None:
    INSTRUCTIONS.parent.mkdir(parents=True, exist_ok=True)
    if text.strip():
        INSTRUCTIONS.write_text(text.rstrip() + "\n")
        INSTRUCTIONS.chmod(0o600)
    elif INSTRUCTIONS.exists():
        INSTRUCTIONS.unlink()


def autostart_enabled() -> bool:
    try:
        return "Hidden=true" not in AUTOSTART.read_text()
    except OSError:
        return True  # the system autostart entry applies


def set_autostart(enabled: bool) -> None:
    if enabled:
        if AUTOSTART.exists():
            AUTOSTART.unlink()
    else:
        AUTOSTART.parent.mkdir(parents=True, exist_ok=True)
        AUTOSTART.write_text("[Desktop Entry]\nType=Application\nName=Friday (background)\n"
                             "Exec=tos-friday --background\nHidden=true\n")


def welcome_enabled() -> bool:
    return not NO_WELCOME.exists()


def set_welcome(enabled: bool) -> None:
    if enabled:
        if NO_WELCOME.exists():
            NO_WELCOME.unlink()
    else:
        NO_WELCOME.parent.mkdir(parents=True, exist_ok=True)
        NO_WELCOME.touch()


def os_version() -> str:
    try:
        for line in Path("/etc/os-release").read_text().splitlines():
            if line.startswith("PRETTY_NAME="):
                return line.split("=", 1)[1].strip('"')
    except OSError:
        pass
    return "unknown"

"""Friday's keyboard shortcut, stored in COSMIC's custom shortcuts:
~/.config/cosmic/com.system76.CosmicSettings.Shortcuts/v1/custom (a RON map of
binding -> action). Only entries whose action runs tos-friday are ever touched;
the user's own shortcuts are kept exactly as written.
"""
from __future__ import annotations

import os
import re
from pathlib import Path

DEFAULT = "Alt+space"
LEGACY = "Super+space"          # v0.7 default; clashed with COSMIC's search on Super
MODIFIERS = ("Super", "Ctrl", "Alt", "Shift")
STATE = Path(os.environ.get("XDG_STATE_HOME", Path.home() / ".local/state")) / "tegendo-os"


def custom_file() -> Path:
    base = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
    return base / "cosmic/com.system76.CosmicSettings.Shortcuts/v1/custom"


# ---- tiny RON map splitter ------------------------------------------------------------
def split_entries(text: str) -> list[str] | None:
    """Top-level `key: value` entries of a RON map, verbatim. None if it isn't a map."""
    body = text.strip()
    if not body:
        return []
    if not (body.startswith("{") and body.endswith("}")):
        return None
    inner, entries, depth, start, in_str, esc = body[1:-1], [], 0, 0, False, False
    for i, ch in enumerate(inner):
        if in_str:
            esc = (ch == "\\") and not esc
            if ch == '"' and not esc:
                in_str = False
            continue
        if ch == '"':
            in_str = True
        elif ch in "([{":
            depth += 1
        elif ch in ")]}":
            depth -= 1
        elif ch == "," and depth == 0:
            entries.append(inner[start:i])
            start = i + 1
    entries.append(inner[start:])
    entries = [e.strip() for e in entries if e.strip()]
    return entries if depth == 0 and not in_str else None


def _parse_binding(entry: str) -> str | None:
    """'(modifiers: [Alt], key: "space"): Spawn(...)' -> 'Alt+space'."""
    m = re.match(r'\(\s*modifiers:\s*\[([^\]]*)\]\s*(?:,\s*key:\s*"([^"]+)")?', entry, re.S)
    if not m:
        return None
    mods = [x.strip() for x in m.group(1).replace("\n", " ").split(",") if x.strip()]
    return "+".join(mods + ([m.group(2)] if m.group(2) else []))


def _is_friday(entry: str) -> bool:
    return bool(re.search(r'Spawn\(\s*"[^"]*tos-friday', entry))


def normalize(combo: str) -> str:
    """'alt+SPACE' -> 'Alt+space'; raises ValueError for anything invalid."""
    parts = [p.strip() for p in combo.split("+") if p.strip()]
    if len(parts) < 2:
        raise ValueError("use at least one modifier, e.g. Alt+space")
    mods, key = parts[:-1], parts[-1]
    canon = {m.lower(): m for m in MODIFIERS} | {"control": "Ctrl", "meta": "Super", "logo": "Super"}
    out = []
    for m in mods:
        if m.lower() not in canon:
            raise ValueError(f"unknown modifier '{m}'")
        out.append(canon[m.lower()])
    if not re.fullmatch(r"[A-Za-z0-9_]{1,24}", key):
        raise ValueError(f"unsupported key '{key}'")
    key = key.lower() if len(key) == 1 or key.lower() in ("space", "return", "tab", "escape") else key
    if key == "return":
        key = "Return"
    ordered = [m for m in MODIFIERS if m in out]
    return "+".join(ordered + [key])


def _entry(combo: str) -> str:
    *mods, key = combo.split("+")
    return f'(modifiers: [{", ".join(mods)}], key: "{key}"): Spawn("tos-friday")'


def current(path: Path | None = None) -> str | None:
    path = path or custom_file()
    try:
        entries = split_entries(path.read_text()) or []
    except OSError:
        return None
    for e in entries:
        if _is_friday(e):
            return _parse_binding(e)
    return None


def set_binding(combo: str, path: Path | None = None) -> str:
    """Point Friday's shortcut at `combo`. Other shortcuts are untouched; a user
    shortcut already on that combo makes this fail rather than steal it."""
    combo = normalize(combo)
    path = path or custom_file()
    text = path.read_text() if path.exists() else ""
    entries = split_entries(text)
    if entries is None:
        raise ValueError(f"{path} isn't a shortcut map this can safely edit")
    taken = [e for e in entries if not _is_friday(e) and (_parse_binding(e) or "").lower() == combo.lower()]
    if taken:
        raise ValueError(f"{combo} is already one of your shortcuts")
    kept = [e for e in entries if not _is_friday(e)]
    body = "".join(f"    {e},\n" for e in kept) + f"    {_entry(combo)},\n"
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text("{\n" + body + "}\n")
    tmp.replace(path)
    return combo


def migrate(path: Path | None = None, state: Path | None = None) -> str:
    """Run by tos-setup on every version. Moves Friday off Super+Space (v0.7),
    adds the default for new users, and never overrides a choice the user made."""
    state = state or STATE
    stamp = state / "friday-shortcut-v2"
    if stamp.exists():
        return "unchanged (already set up)"
    cur = current(path)
    legacy_stamp = (state / "friday-shortcut-added").exists()
    if cur is None and legacy_stamp:
        result = "unchanged (you removed Friday's shortcut)"
    elif cur is None or cur == LEGACY:
        result = f"set to {set_binding(DEFAULT, path)}"
    else:
        result = f"unchanged ({cur}, your choice)"
    state.mkdir(parents=True, exist_ok=True)
    stamp.touch()
    return result


def label(combo: str | None) -> str:
    return combo.replace("+space", "+Space").replace("+", " + ") if combo else "not set"

"""Small Markdown → Pango markup converter for Friday's answers.

Covers what chat answers use: paragraphs, headings, bullets, numbered lists,
**bold**, *italic*, `code`, fenced code blocks and [links](https://…).
Everything is escaped first, so model output can never inject markup.
"""
from __future__ import annotations

import html
import re

_CODE_SPAN = re.compile(r"`([^`\n]+)`")
_BOLD = re.compile(r"\*\*(?=\S)(.+?)(?<=\S)\*\*")
_ITALIC = re.compile(r"(?<![\*\w])\*(?=\S)([^*\n]+?)(?<=\S)\*(?![\*\w])")
_LINK = re.compile(r"\[([^\]\n]+)\]\((https?://[^\s)]+)\)")
_HEADING = re.compile(r"^(#{1,4})\s+(.*)$")
_BULLET = re.compile(r"^(\s*)[-*]\s+(.*)$")
_NUMBERED = re.compile(r"^(\s*)(\d+)[.)]\s+(.*)$")


def esc(text: str) -> str:
    return html.escape(text, quote=True)


def _inline(line: str, code_bg: str) -> str:
    """Escape one line, then apply inline formatting (code spans are protected)."""
    spans: list[str] = []

    def keep_code(m: re.Match) -> str:
        # Non-breaking spaces keep a command on one line instead of wrapping mid-command.
        code = esc(m.group(1)).replace(" ", "\u00a0")
        spans.append(f'<span font_family="monospace" background="{code_bg}">\u00a0{code}\u00a0</span>')
        return f"\x00{len(spans) - 1}\x00"

    line = _CODE_SPAN.sub(keep_code, line)
    links: list[str] = []

    def keep_link(m: re.Match) -> str:
        links.append(f'<a href="{esc(m.group(2))}">{esc(m.group(1))}</a>')
        return f"\x01{len(links) - 1}\x01"

    line = _LINK.sub(keep_link, line)
    line = esc(line)
    line = _BOLD.sub(r"<b>\1</b>", line)
    line = _ITALIC.sub(r"<i>\1</i>", line)
    line = re.sub("\x01(\\d+)\x01", lambda m: links[int(m.group(1))], line)
    line = re.sub("\x00(\\d+)\x00", lambda m: spans[int(m.group(1))], line)
    return line


def to_pango(text: str, code_bg: str = "#13141c", heading_color: str = "#c0caf5") -> str:
    out: list[str] = []
    in_code = False
    code: list[str] = []
    for raw in text.split("\n"):
        if raw.strip().startswith("```"):
            if in_code:
                body = esc("\n".join(code))
                out.append(f'<span font_family="monospace" background="{code_bg}">{body}</span>')
                code = []
            in_code = not in_code
            continue
        if in_code:
            code.append(raw)
            continue
        if m := _HEADING.match(raw):
            out.append(f'<span weight="bold" foreground="{heading_color}">{_inline(m.group(2), code_bg)}</span>')
        elif m := _BULLET.match(raw):
            indent = "    " * (len(m.group(1)) // 2)
            out.append(f"{indent}•  {_inline(m.group(2), code_bg)}")
        elif m := _NUMBERED.match(raw):
            indent = "    " * (len(m.group(1)) // 2)
            out.append(f"{indent}{m.group(2)}.  {_inline(m.group(3), code_bg)}")
        else:
            out.append(_inline(raw, code_bg))
    if in_code:  # unterminated fence while streaming: show it as code so far
        out.append(f'<span font_family="monospace" background="{code_bg}">{esc(chr(10).join(code))}</span>')
    return "\n".join(out).strip("\n")

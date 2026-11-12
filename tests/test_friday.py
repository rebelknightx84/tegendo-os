"""Friday's backends and markup, without a display, Claude account or GPU.

Fakes: a `claude` executable that replays stream-json, an Ollama HTTP server
that asks for one tool call and then answers, and a tiny MCP server.
The real tos-mcp is used where it has no side effects (tool listing).
"""
import json
import os
import stat
import sys
import tempfile
import textwrap
import threading
import unittest
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TMP = Path(tempfile.mkdtemp(prefix="friday-test-"))

# A fake MCP server: one read tool and one system tool.
FAKE_MCP = TMP / "fake-mcp"
FAKE_MCP.write_text(textwrap.dedent("""\
    #!/usr/bin/env python3
    import json, sys
    if sys.argv[1:] == ["--list-tools"]:
        print("read    system_status          System status")
        print("system  system_update          Update system")
        sys.exit(0)
    for line in sys.stdin:
        msg = json.loads(line)
        if "id" not in msg:
            continue
        m, rid = msg["method"], msg["id"]
        if m == "initialize":
            res = {"protocolVersion": "2025-11-25", "capabilities": {"tools": {}}, "serverInfo": {"name": "fake"}}
        elif m == "tools/list":
            res = {"tools": [{"name": "system_status", "description": "[read] status",
                              "inputSchema": {"type": "object", "properties": {}}}]}
        elif m == "tools/call":
            res = {"content": [{"type": "text", "text": "disk / at 91%"}], "isError": False}
        print(json.dumps({"jsonrpc": "2.0", "id": rid, "result": res}), flush=True)
"""))
FAKE_MCP.chmod(FAKE_MCP.stat().st_mode | stat.S_IEXEC)
os.environ["TOS_MCP"] = str(FAKE_MCP)
os.environ["XDG_CONFIG_HOME"] = str(TMP / "config")
os.environ["XDG_STATE_HOME"] = str(TMP / "state")

sys.path.insert(0, str(ROOT / "src/lib"))
from friday import backends  # noqa: E402
from friday.backends import ClaudeBackend, Friday, OllamaBackend, tool_tiers  # noqa: E402
from friday.markup import to_pango  # noqa: E402
from friday.mcp_client import McpClient  # noqa: E402


def fake_claude(events: list[dict], exit_code: int = 0) -> str:
    """An executable that records its argv and prints the given stream-json events."""
    path = TMP / f"claude-{len(events)}-{exit_code}"
    lines = "\n".join(json.dumps(e) for e in events)
    path.write_text(f"#!/bin/sh\nprintf '%s\\n' \"$@\" > '{path}.argv'\ncat <<'EOF'\n{lines}\nEOF\nexit {exit_code}\n")
    path.chmod(0o755)
    return str(path)


CLAUDE_OK = [
    {"type": "system", "subtype": "init", "session_id": "sess-1"},
    {"type": "stream_event", "event": {"type": "content_block_start",
                                        "content_block": {"type": "tool_use", "id": "t1",
                                                          "name": "mcp__tegendo-os__system_update"}}},
    {"type": "user", "message": {"content": [{"type": "tool_result", "tool_use_id": "t1",
                                              "is_error": True, "content": [{"type": "text", "text": "denied by user"}]}]}},
    {"type": "stream_event", "event": {"type": "content_block_delta", "delta": {"type": "text_delta", "text": "No update, "}}},
    {"type": "stream_event", "event": {"type": "content_block_delta", "delta": {"type": "text_delta", "text": "Boss."}}},
    {"type": "result", "subtype": "success", "is_error": False, "session_id": "sess-1", "result": "No update, Boss."},
]
CLAUDE_AUTH_FAIL = [
    {"type": "system", "subtype": "init", "session_id": "sess-x"},
    {"type": "result", "subtype": "error", "is_error": True, "result": "Invalid API key · Please run /login"},
]


class OllamaHandler(BaseHTTPRequestHandler):
    calls: list[dict] = []

    def log_message(self, *a):
        pass

    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b'{"models": []}')

    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        OllamaHandler.calls.append(body)
        self.send_response(200)
        self.end_headers()
        if not any(m["role"] == "tool" for m in body["messages"]):
            chunks = [{"message": {"role": "assistant", "content": "",
                                   "tool_calls": [{"function": {"name": "system_status", "arguments": {}}}]},
                       "done": True}]
        else:
            chunks = [{"message": {"role": "assistant", "content": "Disk is at "}},
                      {"message": {"role": "assistant", "content": "91%."}, "done": True}]
        for c in chunks:
            self.wfile.write((json.dumps(c) + "\n").encode())


def ollama_server() -> str:
    srv = HTTPServer(("127.0.0.1", 0), OllamaHandler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return f"http://127.0.0.1:{srv.server_port}"


def collect(fn, *args):
    events = []
    fn(*args, events.append)
    return events


class MarkupTests(unittest.TestCase):
    def test_escapes_model_output(self):
        out = to_pango('<span foreground="red">x</span> & <b>')
        self.assertNotIn("<span foreground", out)
        self.assertIn("&lt;span", out)

    def test_formatting(self):
        out = to_pango("**bold** *it* `a*b*` [d](https://x.org) [bad](javascript:alert(1))")
        self.assertIn("<b>bold</b>", out)
        self.assertIn("<i>it</i>", out)
        self.assertIn("\u00a0a*b*\u00a0</span>", out)  # no formatting inside code
        self.assertIn("flatpak\u00a0uninstall", to_pango("`flatpak uninstall`"))  # commands don't wrap
        self.assertIn('<a href="https://x.org">d</a>', out)
        self.assertNotIn('href="javascript', out)    # only http(s) links

    def test_code_block_and_lists(self):
        out = to_pango("- one\n2. two\n```\nrm -rf <x>\n```")
        self.assertIn("•  one", out)
        self.assertIn("2.  two", out)
        self.assertIn("rm -rf &lt;x&gt;", out)


class ClaudeTests(unittest.TestCase):
    def test_command_locks_claude_to_tos_mcp(self):
        b = ClaudeBackend({}, claude="/usr/bin/claude")
        cmd = b.command("hi")
        self.assertEqual(cmd[cmd.index("--tools") + 1], "")           # no built-in tools
        self.assertIn("--strict-mcp-config", cmd)                     # no other MCP servers
        mcp = json.loads(cmd[cmd.index("--mcp-config") + 1])
        self.assertEqual(list(mcp["mcpServers"]), ["tegendo-os"])
        self.assertEqual(cmd[cmd.index("--allowedTools") + 1], "mcp__tegendo-os")
        self.assertNotIn("--resume", cmd)
        for forbidden in ("--dangerously-skip-permissions", "bypassPermissions", "Bash"):
            self.assertNotIn(forbidden, " ".join(cmd))

    def test_stream_events_and_resume(self):
        b = ClaudeBackend(tool_tiers(), claude=fake_claude(CLAUDE_OK))
        ev = collect(b.send, "update please")
        types = [e["type"] for e in ev]
        self.assertEqual(types, ["tool_start", "tool_end", "text", "text", "done"])
        self.assertEqual(ev[0]["name"], "system_update")
        self.assertEqual(ev[0]["tier"], "system")                     # so the UI steps aside
        self.assertFalse(ev[1]["ok"])
        self.assertEqual("".join(e["text"] for e in ev if e["type"] == "text"), "No update, Boss.")
        self.assertEqual(b.session_id, "sess-1")
        self.assertIn("--resume", b.command("again"))

    def test_error_result(self):
        b = ClaudeBackend({}, claude=fake_claude(CLAUDE_AUTH_FAIL, exit_code=1))
        ev = collect(b.send, "hi")
        self.assertEqual(ev[-1]["type"], "error")
        self.assertIn("login", ev[-1]["text"])


class OllamaAndFallbackTests(unittest.TestCase):
    def test_tool_loop(self):
        OllamaHandler.calls.clear()
        b = OllamaBackend(ollama_server(), "qwen3:14b", tool_tiers())
        self.assertTrue(b.available())
        ev = collect(b.send, "how full is my disk?")
        self.assertEqual([e["type"] for e in ev], ["tool_start", "tool_end", "text", "text", "done"])
        self.assertTrue(ev[1]["ok"])
        self.assertIn("91%", ev[1]["summary"])
        req = OllamaHandler.calls[0]
        self.assertEqual([t["function"]["name"] for t in req["tools"]], ["system_status"])
        self.assertFalse(req["think"])
        self.assertEqual(req["messages"][0]["role"], "system")
        self.assertEqual(OllamaHandler.calls[1]["messages"][-1]["role"], "tool")

    def test_auto_falls_back_to_local(self):
        conf = Path(os.environ["XDG_CONFIG_HOME"]) / "tegendo-os"
        conf.mkdir(parents=True, exist_ok=True)
        (conf / "agent.conf").write_text(f"TOS_OLLAMA_URL='{ollama_server()}'\nTOS_FRIDAY_BACKEND=auto\n")
        f = Friday()
        f.claude.claude = fake_claude(CLAUDE_AUTH_FAIL, exit_code=1)
        ev = collect(f.send, "disk?")
        types = [e["type"] for e in ev]
        self.assertIn("error", types)
        self.assertIn("note", types)
        self.assertEqual(types[-1], "done")
        self.assertTrue(f.label.startswith("local"))

    def test_agent_conf_is_parsed_not_executed(self):
        conf = Path(os.environ["XDG_CONFIG_HOME"]) / "tegendo-os"
        conf.mkdir(parents=True, exist_ok=True)
        marker = TMP / "pwned"
        (conf / "agent.conf").write_text(f"TOS_OLLAMA_MODEL=$(touch {marker})\n")
        self.assertEqual(backends.read_agent_conf()["TOS_OLLAMA_MODEL"], f"$(touch {marker})")
        self.assertFalse(marker.exists())


class RealToolsTests(unittest.TestCase):
    def test_real_tos_mcp_lists_tools_with_tiers(self):
        real = str(ROOT / "src/bin/tos-mcp")
        c = McpClient([sys.executable, real])
        c.start()
        names = {t["name"] for t in c.tools()}
        c.close()
        self.assertIn("system_status", names)
        self.assertIn("system_update", names)


if __name__ == "__main__":
    unittest.main()

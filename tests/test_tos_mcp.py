"""Tests for tos-mcp and tos-helper.

    python3 -m unittest tests/test_tos_mcp.py -v

The MCP SDK conformance test runs when the `mcp` package is importable
(CI installs it); everything else needs only the standard library.
Dialogs, polkit and system commands are replaced by stubs on PATH, so nothing
here touches the real system.
"""

from __future__ import annotations

import asyncio
import json
import os
import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SERVER = ROOT / "src/bin/tos-mcp"
HELPER = ROOT / "src/libexec/tos-helper"


def stub(bindir: Path, name: str, body: str) -> None:
    p = bindir / name
    p.write_text("#!/bin/sh\n" + textwrap.dedent(body))
    p.chmod(0o755)


class Harness:
    """A throwaway environment with stubbed system commands."""

    def __init__(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        self.bin = self.dir / "bin"
        self.bin.mkdir()
        self.calls = self.dir / "calls.log"
        self.helper = self.dir / "fake-helper"
        self.helper.write_text("#!/bin/sh\n")
        self.helper.chmod(0o755)
        # one line per call, even when an argument (dialog text) spans several lines
        log = f'printf "%s %s\\n" "$0" "$(printf "%s " "$@" | tr "\\n" " ")" >> {self.calls}\n'
        stub(self.bin, "zenity", log + 'case "$(cat %s/zenity.answer 2>/dev/null)" in approve) exit 0;; *) exit 1;; esac\n' % self.dir)
        stub(self.bin, "pkexec", log + 'case "$(cat %s/pkexec.mode 2>/dev/null)" in\n'
             '  cancel) echo "Error executing command as another user: Request dismissed" >&2; exit 126;;\n'
             '  *) echo "pacman output line"; echo \'{"action":"install","rc":0,"pre":141,"post":142}\';;\n'
             'esac\n' % self.dir)
        stub(self.bin, "tos-theme", log + 'case "$1" in list) printf "gruvbox\\ntokyo-night\\n";; current) echo tokyo-night;; set) echo "theme: $2";; esac\n')
        stub(self.bin, "journalctl", log + 'echo "Nov 10 sshd: login from 8.8.8.8 token=hunter2 ghp_ABCDEFGHIJKLMNOPQRSTUVWX1234 by joel@example.com"\n')
        stub(self.bin, "systemctl", log + 'echo "(stub systemctl)"\n')
        stub(self.bin, "checkupdates", log + 'echo "openssl 3.4.0-1 -> 3.4.1-1"\n')
        self.env = {
            "PATH": f"{self.bin}:/usr/bin:/bin",
            "HOME": str(self.dir / "home"),
            "XDG_STATE_HOME": str(self.dir / "state"),
            "TOS_HELPER": str(self.helper),
            "TOS_LIB": str(ROOT / "src/lib"),
            "WAYLAND_DISPLAY": "wayland-0",
            "TOS_CONFIRM_TIMEOUT": "5",
        }

    def answer(self, zenity: str = "approve", pkexec: str = "ok") -> None:
        (self.dir / "zenity.answer").write_text(zenity)
        (self.dir / "pkexec.mode").write_text(pkexec)

    def calls_of(self, name: str) -> list[str]:
        if not self.calls.exists():
            return []
        return [ln.rstrip() for ln in self.calls.read_text().splitlines()
                if ln.split(" ")[0].endswith("/" + name)]

    def audit(self) -> list[dict]:
        f = self.dir / "state/tegendo-os/friday/audit.jsonl"
        return [json.loads(ln) for ln in f.read_text().splitlines()] if f.exists() else []

    def rpc(self, *messages: dict | str, env: dict | None = None) -> list[dict]:
        lines = "".join((m if isinstance(m, str) else json.dumps(m)) + "\n" for m in messages)
        p = subprocess.run([sys.executable, str(SERVER)], input=lines, capture_output=True, text=True,
                           env=env or self.env, timeout=60)
        return [json.loads(ln) for ln in p.stdout.splitlines() if ln.strip()]

    def call(self, tool: str, args: dict | None = None, env: dict | None = None) -> dict:
        out = self.rpc({"jsonrpc": "2.0", "id": 1, "method": "tools/call",
                        "params": {"name": tool, "arguments": args or {}}}, env=env)
        return out[0]["result"]


def text(result: dict) -> str:
    return result["content"][0]["text"]


class ProtocolTests(unittest.TestCase):
    def setUp(self):
        self.h = Harness()

    def tearDown(self):
        self.h.tmp.cleanup()

    def test_handshake_negotiation(self):
        out = self.h.rpc(
            {"jsonrpc": "2.0", "id": 1, "method": "initialize",
             "params": {"protocolVersion": "2025-06-18", "capabilities": {}, "clientInfo": {"name": "t", "version": "1"}}},
            {"jsonrpc": "2.0", "method": "notifications/initialized"},
            {"jsonrpc": "2.0", "id": 2, "method": "initialize", "params": {"protocolVersion": "2099-01-01"}},
            {"jsonrpc": "2.0", "id": 3, "method": "server/discover", "params": {}},
            {"jsonrpc": "2.0", "id": 4, "method": "ping"},
            "{not json",
        )
        self.assertEqual(len(out), 5, "the notification must not get a reply")
        self.assertEqual(out[0]["result"]["protocolVersion"], "2025-06-18")
        self.assertEqual(out[0]["result"]["capabilities"], {"tools": {"listChanged": False}})
        self.assertEqual(out[1]["result"]["protocolVersion"], "2025-11-25")
        self.assertEqual(out[2]["error"]["code"], -32601, "discover must fall back to the handshake")
        self.assertEqual(out[3]["result"], {})
        self.assertEqual(out[4]["error"]["code"], -32700)

    def test_tool_list_shape(self):
        tools = self.h.rpc({"jsonrpc": "2.0", "id": 1, "method": "tools/list"})[0]["result"]["tools"]
        self.assertEqual(len(tools), 19)
        for t in tools:
            self.assertRegex(t["description"], r"^\[(read|user|system)\] ")
            self.assertFalse(t["inputSchema"]["additionalProperties"])
            self.assertEqual(t["annotations"]["readOnlyHint"], t["description"].startswith("[read]"))
            if not t["description"].startswith("[read]"):
                self.assertIn("reason", t["inputSchema"]["required"], t["name"])
        names = {t["name"] for t in tools}
        for forbidden in ("shell", "exec", "run_command", "write_file", "delete_file", "snapshot_undo", "firewall"):
            self.assertFalse(any(forbidden in n for n in names), forbidden)


class ValidationTests(unittest.TestCase):
    def setUp(self):
        self.h = Harness()

    def tearDown(self):
        self.h.tmp.cleanup()

    def assertRejected(self, tool, args, fragment):
        r = self.h.call(tool, args)
        self.assertTrue(r["isError"], (tool, args))
        self.assertIn(fragment, text(r))
        self.assertEqual(self.h.calls_of("zenity"), [], "rejected input must never reach a dialog")

    def test_rejections(self):
        self.assertRejected("system_status", {"extra": 1}, "Unknown arguments")
        self.assertRejected("service_status", {"unit": "--help.service"}, "invalid format")
        self.assertRejected("service_status", {"unit": "foo;rm -rf /.service"}, "invalid format")
        self.assertRejected("package_install", {"packages": ["-Syu"], "reason": "x"}, "invalid item")
        self.assertRejected("package_install", {"packages": [f"p{i}" for i in range(11)], "reason": "x"}, "number of items")
        self.assertRejected("package_install", {"packages": ["vim"]}, "Missing required argument: reason")
        self.assertRejected("journal_errors", {"limit": 5000}, "out of range")
        self.assertRejected("nvidia_runtime_pm", {"enable": "yes", "reason": "x"}, "must be a boolean")
        self.assertRejected("theme_set", {"name": "no-such-theme", "reason": "x"}, "No theme named")
        r = self.h.call("no_such_tool")
        self.assertTrue(r["isError"])


class TierTests(unittest.TestCase):
    def setUp(self):
        self.h = Harness()

    def tearDown(self):
        self.h.tmp.cleanup()

    def test_read_is_automatic_and_redacted(self):
        r = self.h.call("journal_errors", {"since": "1h"})
        self.assertFalse(r["isError"])
        out = text(r)
        for secret in ("8.8.8.8", "hunter2", "ghp_", "joel@example.com"):
            self.assertNotIn(secret, out)
        self.assertIn("[REDACTED-PUBLIC-IP]", out)
        self.assertEqual(self.h.calls_of("zenity"), [])
        self.assertEqual(self.h.audit()[-1]["decision"], "auto")

    def test_user_tier_needs_approval(self):
        self.h.answer(zenity="approve")
        r = self.h.call("theme_set", {"name": "gruvbox", "reason": "you asked for warmer colors"})
        self.assertFalse(r["isError"], text(r))
        self.assertEqual(len(self.h.calls_of("zenity")), 1)
        self.assertTrue(any("set gruvbox" in c for c in self.h.calls_of("tos-theme")))
        self.assertIn("its own claim, not verified", self.h.calls_of("zenity")[0])

    def test_denial_then_throttle(self):
        self.h.answer(zenity="deny")
        args = {"name": "gruvbox", "reason": "x"}
        msgs = [{"jsonrpc": "2.0", "id": i, "method": "tools/call",
                 "params": {"name": "theme_set", "arguments": args}} for i in (1, 2)]
        first, second = (m["result"] for m in self.h.rpc(*msgs))
        self.assertTrue(first["isError"]) and self.assertIn("Denied", text(first))
        self.assertTrue(second["isError"])
        self.assertIn("denied this exact request moments ago", text(second))
        self.assertEqual(len(self.h.calls_of("zenity")), 1, "a denial must not re-prompt")
        self.assertFalse(any(" set " in c for c in self.h.calls_of("tos-theme")))
        self.assertEqual([a["decision"] for a in self.h.audit()], ["denied", "throttled"])

    def test_no_display_means_no(self):
        env = {k: v for k, v in self.h.env.items() if k != "WAYLAND_DISPLAY"}
        self.h.answer(zenity="approve")
        r = self.h.call("theme_set", {"name": "gruvbox", "reason": "x"}, env=env)
        self.assertTrue(r["isError"])
        self.assertEqual(self.h.calls_of("zenity"), [])

    def test_system_tier_goes_through_polkit_with_snapshots(self):
        self.h.answer(zenity="approve", pkexec="ok")
        r = self.h.call("package_install", {"packages": ["nvidia-prime"], "reason": "hybrid GPU"})
        self.assertFalse(r["isError"], text(r))
        self.assertIn("tos undo 141", text(r))
        pk = self.h.calls_of("pkexec")
        self.assertEqual(len(pk), 1)
        self.assertTrue(pk[0].endswith(f"{self.h.helper} install nvidia-prime"), pk[0])
        last = self.h.audit()[-1]
        self.assertEqual((last["decision"], last["snapshot_pre"], last["snapshot_post"]), ("approved", 141, 142))

    def test_system_tier_denied_never_reaches_polkit(self):
        self.h.answer(zenity="deny")
        r = self.h.call("system_update", {"reason": "x"})
        self.assertTrue(r["isError"])
        self.assertEqual(self.h.calls_of("pkexec"), [])

    def test_password_cancel(self):
        self.h.answer(zenity="approve", pkexec="cancel")
        r = self.h.call("service_restart", {"unit": "bluetooth.service", "reason": "x"})
        self.assertTrue(r["isError"])
        self.assertIn("password prompt was cancelled", text(r))
        self.assertEqual(self.h.audit()[-1]["decision"], "password-cancelled")

    def test_audit_file_is_private(self):
        self.h.call("system_status")
        f = self.h.dir / "state/tegendo-os/friday/audit.jsonl"
        self.assertEqual(f.stat().st_mode & 0o777, 0o600)


@unittest.skipUnless(os.geteuid() == 0, "helper validation tests need root (they stop before changing anything)")
class HelperTests(unittest.TestCase):
    def helper(self, *args: str) -> subprocess.CompletedProcess:
        return subprocess.run(["bash", str(HELPER), *args], capture_output=True, text=True, timeout=30,
                              env={"PATH": "/usr/bin:/bin", "PKEXEC_UID": "1000"})

    def test_refusals(self):
        for args, why in [(("install", "--root=/tmp"), "invalid package"),
                          (("install",), "1-10 packages"),
                          (("restart", "dbus.service"), "not allowed"),
                          (("restart", "-x.service"), "invalid unit"),
                          (("nvidia-pm", "maybe"), "on|off"),
                          (("rm", "-rf", "/"), "unknown action")]:
            p = self.helper(*args)
            self.assertEqual(p.returncode, 2, (args, p.stderr))
            self.assertIn(why, p.stderr)
            self.assertEqual(json.loads(p.stdout.splitlines()[-1])["rc"], 2)

    def test_refuses_without_snapper(self):
        if subprocess.run(["sh", "-c", "snapper -c root get-config"], capture_output=True).returncode == 0:
            self.skipTest("this machine has a real Snapper config")
        p = self.helper("install", "vim")
        self.assertEqual(p.returncode, 2)
        self.assertIn("no safety snapshot", p.stderr)


try:
    import mcp  # noqa: F401
    HAVE_SDK = True
except ImportError:
    HAVE_SDK = False


@unittest.skipUnless(HAVE_SDK, "official MCP SDK not installed")
class SDKConformanceTests(unittest.TestCase):
    """A real MCP client connects the way Claude Code and others do."""

    def test_official_client(self):
        from mcp import ClientSession, StdioServerParameters
        from mcp.client.stdio import stdio_client
        try:
            from mcp.client._probe import negotiate_auto
        except ImportError:  # older SDKs: plain handshake
            negotiate_auto = None

        h = Harness()
        self.addCleanup(h.tmp.cleanup)
        params = StdioServerParameters(command=str(SERVER), args=[], env=h.env)

        async def go():
            async with stdio_client(params) as (read, write):
                async with ClientSession(read, write) as s:
                    if negotiate_auto:
                        await negotiate_auto(s)  # probes server/discover, falls back to initialize
                    else:
                        await s.initialize()
                    tools = await s.list_tools()
                    status = await s.call_tool("system_status", {})
                    bad = await s.call_tool("service_status", {"unit": "--help.service"})
                    return s.protocol_version, tools, status, bad

        version, tools, status, bad = asyncio.run(go())
        self.assertEqual(version, "2025-11-25")
        self.assertEqual(len(tools.tools), 19)
        self.assertFalse(status.is_error)
        self.assertIn("kernel:", status.content[0].text)
        self.assertTrue(bad.is_error)


if __name__ == "__main__":
    unittest.main()

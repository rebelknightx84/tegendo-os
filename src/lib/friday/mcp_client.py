"""Minimal MCP client (stdio, JSON-RPC) for tos-mcp. Used by the local-model
backend, which has no MCP support of its own. Approval dialogs still come from
tos-mcp itself, so this client can't bypass them."""
from __future__ import annotations

import json
import subprocess
import threading

PROTOCOL = "2025-11-25"


class McpError(RuntimeError):
    pass


class McpClient:
    def __init__(self, command: list[str]):
        self.command = command
        self.proc: subprocess.Popen | None = None
        self._id = 0
        self._lock = threading.Lock()

    def start(self) -> None:
        self.proc = subprocess.Popen(
            self.command, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL, text=True, bufsize=1)
        self._request("initialize", {
            "protocolVersion": PROTOCOL,
            "capabilities": {},
            "clientInfo": {"name": "friday", "version": "0.1.0"},
        })
        self._send({"jsonrpc": "2.0", "method": "notifications/initialized"})

    def close(self) -> None:
        if self.proc and self.proc.poll() is None:
            self.proc.stdin.close()
            self.proc.stdout.close()
            try:
                self.proc.wait(timeout=3)
            except subprocess.TimeoutExpired:
                self.proc.kill()

    def _send(self, msg: dict) -> None:
        assert self.proc and self.proc.stdin
        self.proc.stdin.write(json.dumps(msg) + "\n")
        self.proc.stdin.flush()

    def _request(self, method: str, params: dict) -> dict:
        with self._lock:
            self._id += 1
            rid = self._id
            self._send({"jsonrpc": "2.0", "id": rid, "method": method, "params": params})
            assert self.proc and self.proc.stdout
            for line in self.proc.stdout:
                try:
                    msg = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if msg.get("id") != rid:
                    continue  # notifications or stray responses
                if "error" in msg:
                    raise McpError(msg["error"].get("message", "MCP error"))
                return msg.get("result", {})
            raise McpError("tos-mcp exited")

    def tools(self) -> list[dict]:
        return self._request("tools/list", {}).get("tools", [])

    def call(self, name: str, arguments: dict) -> tuple[bool, str]:
        """Returns (ok, text)."""
        res = self._request("tools/call", {"name": name, "arguments": arguments or {}})
        text = "\n".join(c.get("text", "") for c in res.get("content", []) if c.get("type") == "text")
        return (not res.get("isError", False), text)

# AI on tegendo-os

## Pick an agent

Edit `~/.config/tegendo-os/agent.conf` (created on first login by `tos setup`).
It's read as `KEY=value` lines. Friday (Super+Space) uses Claude first and the
`ollama` settings as its fallback; `tos agent` and `tos doctor` use `TOS_AGENT`.

| Agent | Where data goes | Can it act? | Setup |
|---|---|---|---|
| `claude` | Anthropic (cloud) | yes, asks before each command or edit | install Claude Code (its native installer, into your home folder) |
| `codex` | OpenAI (cloud) | yes, asks for anything untrusted | install Codex CLI |
| `ollama` | your network only | in `tos agent`: **no**, advice only. As Friday's fallback: tos-mcp's tools, with the same approval dialogs | `TOS_OLLAMA_URL=http://your-ollama-host:11434` (e.g. over Tailscale) and `TOS_OLLAMA_MODEL=qwen3:14b` |
| `custom` | your call | your call | `TOS_AGENT_CMD=opencode` etc. (prompt appended as one argument) |

## What `tos doctor` sends

1. **Collects, read-only, without sudo:** OS, kernel, failed units, this boot's
   errors, kernel warnings, core dumps (7 days), recent upgrades, pending
   updates (OS image and Flatpaks), installed Flatpaks, disk, memory, SELinux denials, GPU, network, DNS. For crashes it
   adds `coredumpctl info` and that PID's journal lines.
2. **Redacts:** private keys, GitHub/AWS/Slack/OpenAI-style tokens, JWTs,
   `password=`/`token=`-style values, emails, MAC addresses, public IPs,
   Tailscale auth keys, and your username and hostname. Private and tailnet IPs
   stay, because they matter for debugging.
3. **Saves** to `~/.local/state/tegendo-os/doctor/<time>/report.md` (0600).
4. **Asks** "Send it? [y/N]" and names the destination. `--collect-only`
   never sends.

Redaction is pattern-based. It catches the common shapes, not everything.
For a cloud agent, skim the report first when in doubt.

## Rules the agent is given

Every hand-off includes them, and the tegendo-os skill repeats them:
investigate read-only first, ask before every change, prefer the tegendo-os
MCP tools (they gate changes), put persistent fixes in the repo (the image),
never install system packages live or weaken security, no curl-pipe-to-shell.

## Crash notifications

`tos-crash-watch` (systemd user service) watches systemd-coredump for
crashes of **your** processes only, at most one notification per program per
minute. Clicking "Diagnose" opens Kitty running `tos doctor crash <pid>`,
which still asks before sending. "Don't show again" mutes that program
(`~/.config/tegendo-os/crash-mute/<name>`; delete the file to unmute).

Turn it off with `systemctl --user disable --now tos-crash-watch`.

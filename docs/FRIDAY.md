# Friday: the AI built into tegendo-os

Friday is Claude (or a local model) connected to the OS through **tos-mcp**,
an MCP server. Any MCP client can use it; Claude Code is the default.

```bash
claude mcp add --scope user tegendo-os -- tos-mcp   # done by `tos setup` if Claude Code is installed
tos-mcp --list-tools                                # what Friday can do
tos friday-log                                      # what Friday did
tos undo                                            # boot the previous OS image (only you can)
```

## Alt+Space

Press **Alt+Space** anywhere and Friday drops down over your windows (Esc
hides it; press again to toggle). Ask in plain words, or pick a starter:
"What needs my attention?", "Any updates waiting?", "Why is my disk filling
up?", "Did anything crash recently?". Friday checks the real state with the
tools below, shows each one it uses (✓ done, ✗ denied), and answers.

- **Brain:** Claude through Claude Code when it's installed and signed in;
  otherwise, or if Claude can't answer, your local model (Ollama).
- **Only tegendo-os tools.** Claude Code runs with `--tools ""` (no shell,
  files or web), `--strict-mcp-config` (none of your other MCP servers) and
  only tos-mcp. The local model gets exactly the same tos-mcp tools.
- **Approvals stay the OS's.** When Friday calls a user or system tool it
  hides itself, so the approval dialog is never underneath it, and comes
  back when you've answered.
- **Conversation:** kept while Friday runs (Ctrl+N starts a new one). Claude
  Code stores its sessions in `~/.claude`, as for any Claude Code use.

### Settings (gear icon, Ctrl+, or "Friday Settings" in the app menu)

| Setting | Stored in |
|---|---|
| Answer with: Claude then local / Claude only / local only; Claude model; local model server and model, with a connection test | `~/.config/tegendo-os/agent.conf` (`TOS_FRIDAY_BACKEND`, `TOS_FRIDAY_MODEL`, `TOS_OLLAMA_URL`, `TOS_OLLAMA_MODEL`) |
| Shortcut: press a new combo, or reset to Alt+Space | COSMIC's custom shortcuts; only Friday's entry is touched, and a combo you already use is refused |
| Your instructions: tone, what to call you, what to always check | `~/.config/tegendo-os/friday.md`, added to Friday's system prompt |
| Start with your session (instant open) | `~/.config/autostart/tos-friday.desktop` (`Hidden=true` turns it off) |
| Terminal welcome | `~/.config/tegendo-os/no-welcome` (present = off) |
| Activity log; clear conversation | `~/.local/state/tegendo-os/friday/audit.jsonl` |

From a terminal: `tos-friday --shortcut`, `tos-friday --set-shortcut Super+d`.

**Why not Super+Space:** v0.7 used it, but COSMIC opens its search when Super
is released, so the two fought. Machines that had it are moved to Alt+Space
once, by `tos-setup`; a shortcut you picked yourself is never changed.

## Permission tiers, enforced by the OS

The AI client's own approval prompts are a convenience. They can be
auto-approved, and a prompt-injected model can argue its way past them. So
tos-mcp enforces its own gates, outside the model's reach:

| Tier | Tools | Gate |
|---|---|---|
| **read** | system_status, journal_errors, service_status, failed_units, recent_crashes, package_info, pending_updates, deployments, flatpak_search, request_system_package, gpu_status, disk_usage, network_status, theme_list, activity_log | automatic; all output redacted (`request_system_package` only explains, never changes) |
| **user** | theme_set, user_service_restart, flatpak_install (your user only, Flathub) | native dialog (zenity) showing the exact change; denies with no screen session |
| **system** | system_update, service_restart, nvidia_runtime_pm | dialog, then polkit password (every time, `auth_admin`), run by `tos-helper`; OS updates are staged images (old one stays bootable), `/etc` edits are backed up |
| **never** | shell, file writes or deletes, disks, firewall, users/sudo, rollback, live package installs (`rpm-ostree install`/`dnf`) | no tool exists |

Details that matter:

- **The AI's reason is labelled as unverified.** Dialogs show the exact change
  (computed by tos-mcp) separately from "Friday's reason (its own claim, not verified)".
- **A denial sticks.** The same request can't re-prompt for 60 seconds, so a
  looping or manipulated model can't spam dialogs until you click yes.
- **No screen, no change.** Without a graphical session, user and system tools deny.
- **Inputs are validated twice**, by tos-mcp and again by the root helper,
  which trusts nothing from its caller. Unit names can't start with `-`;
  package names and Flatpak IDs are strict; system packages can only be *requested*
  (`request_system_package` tells you what to add to `image/packages.txt`).
- **Footgun units are refused**: logind, the display manager, dbus, polkit, journald.
- **Atomic or nothing.** The helper refuses to run on anything but an ostree/bootc
  system, and OS updates are only ever *staged*: you choose when to reboot,
  and the previous image stays one `tos undo` away.
- **Two audit trails.** `~/.local/state/tegendo-os/friday/audit.jsonl` (0600,
  every call and decision) and the journal (`journalctl -t tos-helper`, root
  actions, out of the AI's reach). Both are ready for Wazuh.

## Honest limits

- **Origin labels are next.** Friday's window now knows which text you typed
  and which came from tool output, which is what origin labels need; showing
  them in tos-mcp's dialogs is the next step.
- **Origin labels aren't possible in plain MCP clients.** An MCP server can't tell whether
  a request came from you or from a web page the AI read. The mockup's
  "Origin: you asked" and auto-blocking need the Friday front end (panel or
  Alt+Space), which knows what content entered the conversation. Until then
  the gate is you, reading the dialog.
- **Read tools are automatic**, so logs reach the AI after redaction.
  Redaction is pattern-based, not perfect.
- **`nvidia_runtime_pm`** only writes the documented driver option, and
  rebuilds the initramfs when NVIDIA modules are in it. Recent drivers often
  manage power well by default; check `gpu_status` first.

## Protocol

MCP over stdio, standard library only (no third-party packages to vet). It
speaks the `initialize` handshake (2024-11-05 → 2025-11-25), which every
client supports; clients that try the newer `server/discover` (2026-07-28)
fall back automatically. CI connects with the official MCP Python SDK to
prove it.

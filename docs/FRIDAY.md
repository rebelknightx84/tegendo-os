# Friday: the AI built into tegendo-os

Friday is Claude (or a local model) connected to the OS through **tos-mcp**,
an MCP server. Any MCP client can use it; Claude Code is the default.

```bash
claude mcp add --scope user tegendo-os -- tos-mcp   # done by `tos apply` if Claude Code is installed
tos-mcp --list-tools                                # what Friday can do
tos friday-log                                      # what Friday did
tos undo <snapshot>                                 # revert a Friday change (only you can)
```

## Permission tiers, enforced by the OS

The AI client's own approval prompts are a convenience. They can be
auto-approved, and a prompt-injected model can argue its way past them. So
tos-mcp enforces its own gates, outside the model's reach:

| Tier | Tools | Gate |
|---|---|---|
| **read** | system_status, journal_errors, service_status, failed_units, recent_crashes, package_info, pending_updates, snapshots, gpu_status, disk_usage, network_status, theme_list, activity_log | automatic; all output redacted |
| **user** | theme_set, user_service_restart | native dialog (zenity) showing the exact change; denies with no screen session |
| **system** | package_install, system_update, service_restart, nvidia_runtime_pm | dialog, then polkit password (every time, `auth_admin`), run by `tos-helper` between Snapper pre/post snapshots |
| **never** | shell, file writes or deletes, disks, firewall, users/sudo, pacman.conf, snapshot rollback | no tool exists |

Details that matter:

- **The AI's reason is labelled as unverified.** Dialogs show the exact change
  (computed by tos-mcp) separately from "Friday's reason (its own claim, not verified)".
- **A denial sticks.** The same request can't re-prompt for 60 seconds, so a
  looping or manipulated model can't spam dialogs until you click yes.
- **No screen, no change.** Without a graphical session, user and system tools deny.
- **Inputs are validated twice**, by tos-mcp and again by the root helper,
  which trusts nothing from its caller. Unit names can't start with `-`;
  package names are strict; at most 10 packages per install; repos only, no AUR.
- **Footgun units are refused**: logind, the display manager, dbus, polkit, journald.
- **No snapshot, no change.** The helper refuses system changes when Snapper
  has no `root` config.
- **Two audit trails.** `~/.local/state/tegendo-os/friday/audit.jsonl` (0600,
  every call and decision) and the journal (`journalctl -t tos-helper`, root
  actions, out of the AI's reach). Both are ready for Wazuh.

## Honest limits

- **Origin labels aren't possible here yet.** An MCP server can't tell whether
  a request came from you or from a web page the AI read. The mockup's
  "Origin: you asked" and auto-blocking need the Friday front end (panel or
  Super+Space), which knows what content entered the conversation. Until then
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

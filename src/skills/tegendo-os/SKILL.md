---
name: tegendo-os
description: >
  How this machine is built and the rules for changing it. Use whenever you
  troubleshoot, diagnose, configure, or change anything on this computer:
  packages, drivers, desktop (COSMIC), themes, services, boot, networking,
  firewall, crashes, or "why is X broken". Read before running any command
  that changes system state.
---

# tegendo-os

A personal distribution: **CachyOS** (Arch-based) underneath, the **COSMIC**
desktop on top, and a small layer of config and tools called tegendo-os,
managed declaratively with **Ansible**.

It is **not Omarchy**. It borrows Omarchy's themes and crash-diagnosis
method only. Never suggest `omarchy` commands, never add Omarchy's pacman
repo, and never report issues to Omarchy.

## Layout

| What | Where |
|---|---|
| Source of truth for config | the tegendo-os git repo (usually `~/tegendo-os`), `ansible/` |
| Installed tools | `/usr/local/bin/tos*` |
| Shared data (themes, skills, COSMIC palettes) | `/usr/share/tegendo-os/` |
| User config | `~/.config/tegendo-os/` (agent.conf, themes/, themed/, hooks/, crash-mute/) |
| Active theme (generated) | `~/.local/state/tegendo-os/current/theme/` |
| Doctor reports | `~/.local/state/tegendo-os/doctor/<timestamp>/report.md` |
| Desktop config | `~/.config/cosmic/` (cosmic-config: one file per key) |

Useful commands: `tos theme list|set <name>|current`, `tos doctor`,
`tos update`, `tos status`, `tos friday-log`.

## Prefer the tegendo-os MCP tools

When the `tegendo-os` MCP server (tos-mcp) is connected, use its tools
instead of shell commands. Read tools (`system_status`, `journal_errors`,
`gpu_status`, `snapshots`, …) are redacted and need no approval. Change tools
show the person a dialog; system tools also need their password and run
between Snapper snapshots automatically, so don't take your own snapshot for
them. Always fill `reason` honestly: the person sees it, labelled as your
claim. A denied request means no: don't retry it, don't route around it with
a shell command. Rollback is the person's (`tos undo <snapshot>`), not yours.

## Rules

1. **Investigate read-only first.** `journalctl`, `systemctl status`,
   `coredumpctl`, `pacman -Qi`, reading files. Show evidence before proposing.
2. **Ask before every change.** Say what you'll change, why, and how to undo it.
3. **Snapshot before system changes.** `sudo snapper -c root create -d "pre-agent: <what>"`.
   Root is Btrfs with Snapper; `snap-pac` also snapshots around every pacman run.
4. **Persistent fixes belong in the repo.** If a fix should survive a rebuild,
   propose the change to the Ansible role in `~/tegendo-os/ansible/roles/`
   instead of (or in addition to) editing the live system.
5. **Package sources are fixed.** Do not edit the repo sections of
   `/etc/pacman.conf` or add repositories. CachyOS's repos plus Arch's are
   the only sources. AUR packages go through `paru`, and the PKGBUILD must be
   shown to the user before building.
6. **Never weaken security to make something work**: don't disable the
   firewall (ufw), Secure Boot, or disk encryption, don't add
   NOPASSWD sudo, don't open ports publicly. Find the narrow fix.
7. **No curl-pipe-to-shell.** Download, show, then run if approved.
8. **Separate proof from inference** in what you report.

## System facts

- Kernel: CachyOS kernels (`linux-cachyos`, often `linux-cachyos-lts` too).
  Bootloader is usually **Limine**; kernel cmdline lives in
  `/etc/default/limine`, applied with `sudo limine-update`. Gotcha: confirm
  `nvidia_drm.modeset=1` reached the **LTS** entries too.
- GPU: varies by machine. Check the "Graphics devices" section of the doctor
  report or `lspci -nn | grep -iE 'vga|3d|display'`. Laptops may be hybrid
  (AMD/Intel integrated + NVIDIA discrete, PRIME render offload; the NVIDIA GPU
  should power down when idle). NVIDIA drivers are chosen and managed by
  CachyOS's `chwd` (`chwd --list-installed`); don't hand-install a different branch.
- Display: Wayland, COSMIC compositor (`cosmic-comp`). Floating windows by
  default; tiling is a per-workspace toggle.
- Theme pipeline: `tos theme set` renders Omarchy-format templates and imports
  `cosmic-theme.ron` with `cosmic-settings appearance import`. To fix theme
  output, change templates in `~/.config/tegendo-os/themed/`, never the
  vendored copies in `/usr/share/tegendo-os/themed/`.
- Firewall: `ufw`, default deny incoming, Tailscale interface allowed.
- Remote access: Tailscale. SSH server is off unless the user enabled it.
- Docker publishes ports through iptables **around** ufw. Bind container
  ports to 127.0.0.1 unless the user explicitly wants them reachable.

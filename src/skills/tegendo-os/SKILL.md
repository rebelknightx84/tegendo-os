---
name: tegendo-os
description: >
  How this machine is built and the rules for changing it. Use whenever you
  troubleshoot, diagnose, configure, or change anything on this computer:
  packages, apps, drivers, desktop (COSMIC), themes, services, boot,
  networking, firewall, crashes, or "why is X broken". Read before running
  any command that changes system state.
---

# tegendo-os

A personal distribution built as a **bootc image**: **Fedora COSMIC Atomic**
underneath, plus a layer called tegendo-os (tools, themes, Friday, hardening),
all defined in one git repo and built by CI. The running OS (`/usr`) is
read-only and replaced as a whole on update; the previous image stays
bootable.

It is **not Omarchy**. It borrows Omarchy's themes and crash-diagnosis
method only. Never suggest `omarchy` commands or report issues to Omarchy.

## Layout

| What | Where |
|---|---|
| Source of truth | the tegendo-os git repo: `image/Containerfile`, `image/packages.txt`, `image/build.sh` |
| Tools | `/usr/bin/tos*`; root helper `/usr/lib/tegendo-os/tos-helper` (via polkit only) |
| Shared data (themes, skills, palettes) | `/usr/share/tegendo-os/` (read-only, from the image) |
| User config | `~/.config/tegendo-os/` (agent.conf, themes/, themed/, hooks/, crash-mute/) |
| Active theme (generated) | `~/.local/state/tegendo-os/current/theme/` |
| Doctor reports | `~/.local/state/tegendo-os/doctor/<timestamp>/report.md` |
| Friday audit log | `~/.local/state/tegendo-os/friday/audit.jsonl` |
| Desktop config | `~/.config/cosmic/` (cosmic-config: one file per key) |

Commands: `tos status`, `tos update`, `tos undo`, `tos theme list|set <name>`,
`tos doctor`, `tos setup`, `tos friday-log`.

## Prefer the tegendo-os MCP tools

When the `tegendo-os` MCP server (tos-mcp) is connected, use its tools
instead of shell commands. Read tools (`system_status`, `journal_errors`,
`gpu_status`, `deployments`, …) are redacted and need no approval. Change
tools show the person a dialog; system tools also need their password.
Always fill `reason` honestly: the person sees it, labelled as your claim. A
denied request means no: don't retry it, don't route around it with a shell
command. Rollback is the person's (`tos undo`), not yours.

## Where software goes (this is an atomic OS)

1. **Desktop apps → Flatpak** from Flathub, per user (`flatpak_search`,
   `flatpak_install`). First choice for anything with a GUI.
2. **CLI and dev tools, Ubuntu/Debian-only software → Distrobox**
   (`distrobox create`, then install inside it). Doesn't touch the OS.
3. **System packages → the image.** The person adds the package to
   `image/packages.txt`, CI builds a signed image, `tos update` stages it.
   Use `request_system_package` to give them the exact steps.
   **Never** use `rpm-ostree install` (live layering) or `dnf` on the host:
   it drifts the machine away from its image.
4. Official Fedora repos only. No COPR, no third-party repos, no RPMs
   downloaded from websites, unless the person decides to add one to the
   image themselves. The one standing exception is RPM Fusion for the
   NVIDIA driver, used only at image build time (`image/nvidia/`).
5. **Image-wide Flatpaks** (Steam, ProtonUp-Qt, Protontricks, MangoHud,
   gamescope, Flatseal) are listed in `image/flatpaks.txt` and installed
   system-wide on boot by `tos-flatpak-provision.service`. To add one for
   every machine, the person adds a line there.

## Rules

1. **Investigate read-only first.** Show evidence before proposing.
2. **Ask before every change.** Say what you'll change, why, and how to undo it.
3. **Persistent changes belong in the repo** (the image or the person's
   dotfiles), not hand-edited onto one machine.
4. **Never weaken security to make something work**: don't disable
   SELinux (`setenforce 0`), firewalld, Secure Boot or disk encryption,
   don't add NOPASSWD sudo, don't open ports publicly. For an SELinux
   denial, find the narrow fix (a boolean, a label, a context) and show it.
5. **No curl-pipe-to-shell.** Download, show, then run if approved.
6. **Separate proof from inference** in what you report.

## System facts

- OS: Fedora COSMIC Atomic (current release), as a bootc image from
  `ghcr.io/<owner>/tegendo-os`. `rpm-ostree status` shows the running,
  staged and rollback images. Updates are explicit (`tos update`); the
  auto-apply timer is disabled.
- Security: SELinux enforcing; firewalld default zone `tegendo` (drops all
  inbound except DHCPv6), `tailscale0` in the trusted zone; SSH off by
  default, key-only if enabled.
- GPU: varies by machine. Check `gpu_status` or
  `lspci -nn | grep -iE 'vga|3d|display'`. Laptops may be hybrid
  (AMD/Intel integrated + NVIDIA discrete). The NVIDIA driver (open kernel
  modules, from RPM Fusion) is in the image, signed with the person's own
  Machine Owner Key. With Secure Boot on, the modules load only after
  `tos mok enroll` and a reboot; `tos mok status` shows where that stands.
  If `nvidia-smi` fails with Secure Boot on, check enrollment first, not
  the driver. Never suggest disabling Secure Boot or installing akmods/DKMS.
- Gaming: Steam is the Flatpak (`com.valvesoftware.Steam`); Proton versions
  via ProtonUp-Qt; per-game fixes via Protontricks; launch options like
  `mangohud %command%` or `gamescope -- %command%`. Controller udev rules
  come from the `steam-devices` package in the image.
- `/etc` is writable and merged across updates; `/usr` is read-only;
  `/var` and `/home` are machine state.
- Display: Wayland, COSMIC compositor (`cosmic-comp`). Terminal: Kitty.
- Theme pipeline: `tos theme set` renders Omarchy-format templates and
  imports `cosmic-theme.ron` with `cosmic-settings appearance import`.
  Change templates in `~/.config/tegendo-os/themed/`, never the image copies.
- Containers: Podman (rootless) is the default and respects the firewall.
  If Docker is ever added, its published ports bypass firewalld rules: bind
  to 127.0.0.1 unless exposure is intended.

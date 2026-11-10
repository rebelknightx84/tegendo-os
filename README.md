# tegendo-os

**Fedora COSMIC Atomic + Friday + the best of Omarchy, as one signed image.**

A personal operating system defined in this repo and built by CI as a
[bootc](https://containers.github.io/bootc/) image. Your machines run that
image, update to new versions of it atomically, and can always boot the
previous one.

| | Omarchy | tegendo-os |
|---|---|---|
| Base | Arch + its own pacman repo | Fedora COSMIC Atomic (official), as a bootc image |
| Desktop | Hyprland + Quickshell | COSMIC (floating by default, tiling per workspace) |
| Updates | pushed from Omarchy's repo | images you build, sign and choose to apply; nothing upstream lands unreviewed |
| AI agents | launched with `--yolo` / auto-approve | Friday: OS-enforced approvals, no shell, no live package installs |

## What you get

- **Friday (tos-mcp)**: Claude, or any MCP client, connected to the OS.
  Reading is automatic and redacted; your settings and Flatpak apps need a
  click; system changes need a click plus your password. There's no shell
  tool. See [docs/FRIDAY.md](docs/FRIDAY.md).
- **Omarchy's 22 themes**: `tos theme set tokyo-night` recolors COSMIC
  (accent, background, wallpaper), Kitty and btop, and generates matching
  configs for Alacritty, Foot, Helix, Neovim, VS Code and more.
- **AI troubleshooting**: `tos doctor "why does wifi drop?"` collects
  read-only diagnostics, scrubs secrets, shows you what it'll send, then hands
  off to Claude Code, Codex, or a local Ollama model.
- **Crash watcher**: a notification offers "Diagnose with AI" when one of
  your apps crashes.
- **Hardening**: SELinux enforcing, a firewall zone that drops inbound
  traffic, key-only SSH (off by default), official Fedora repos only, signed
  images, explicit updates.
- **Software, the atomic way**: desktop apps as Flatpaks, dev and
  Ubuntu-only tools in Distrobox, system packages in `image/packages.txt`.

## Install

1. Install **Fedora COSMIC Atomic** from Fedora's official ISO. Write it with
   Fedora Media Writer or `dd` (not Ventoy), and turn on disk encryption.
2. Switch to the tegendo-os image and reboot:
   ```bash
   sudo bootc switch ghcr.io/rebelknightx84/tegendo-os:45
   systemctl reboot
   ```
3. Log in. `tos-setup` runs once on its own (theme, Friday, Flathub).
   Check with `tos status`.

If the image is private, add a read-only registry token to
`/etc/ostree/auth.json` first (see [docs/SECURITY.md](docs/SECURITY.md)).

## Commands

```
tos status                     # image, version, theme, health
tos update                     # stage the newest image + update Flatpaks (reboot to apply)
tos undo                       # boot the previous image (only you can; Friday can't)
tos theme list | current | set <name>
tos doctor [question]          tos doctor crash <pid>
tos agent "prompt"
tos setup [--force]            # re-run per-user setup
tos friday-log                 # what Friday did
tos-mcp --list-tools           # Friday's tools and their tiers
```

## Changing the OS

Edit the repo, open a PR, merge when CI is green, then `tos update` on each
machine. To add a system package, add a line to `image/packages.txt`
(official Fedora repos only).

## Layout

```
image/Containerfile     the OS: Fedora COSMIC Atomic + build.sh
image/build.sh          installs packages, tools, data, hardening (runs at build time only)
image/packages.txt      system packages, official repos only
image/system/           firewalld zone, sshd drop-in
src/bin/                tos, tos-theme, tos-mcp, tos-doctor, tos-agent, tos-crash-watch, tos-setup
src/lib/                tos_redact.py (shared secret scrubbing)
src/libexec/tos-helper  the only code Friday can run as root (via polkit)
src/polkit/             password-every-time policy for tos-helper
src/skills/             the tegendo-os skill (teaches agents how this system works)
src/share/cosmic/       COSMIC base palettes (from libcosmic, MPL-2.0)
vendor/omarchy/         pinned, data-only slice of Omarchy (themes, templates, crash skill)
tools/upstream-sync.sh  the only way upstream content enters this repo
tests/                  renderer parity, COSMIC theme parsing, tos-mcp (incl. a real MCP client)
.github/workflows/      ci.yml (lint + tests), image.yml (build, push, sign)
```

## Docs

- [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md): how the pieces fit and the trust model
- [docs/FRIDAY.md](docs/FRIDAY.md): tos-mcp, permission tiers, honest limits
- [docs/SECURITY.md](docs/SECURITY.md): what's hardened, supply chain, what to watch
- [docs/UPSTREAM.md](docs/UPSTREAM.md): pulling new Omarchy themes safely
- [docs/AI.md](docs/AI.md): agents, privacy, local models

## Roadmap

1. **Done:** themes, doctor, crash watcher; Friday's OS connector (tos-mcp).
2. **Now (v0.3):** Fedora COSMIC Atomic bootc image, built and signed in CI.
3. **Next:** NVIDIA in the image (signed kernel module), signature-enforced
   updates, Friday's Super+Space assistant and proactive watchers.
4. **Later:** a COSMIC panel applet for Friday; an installer ISO from the same
   image (interactive, never an unattended disk wipe), with known hardware
   fixes applied automatically.

## Credits

Themes, templates and the diagnose-crash skill are from
[Omarchy](https://github.com/basecamp/omarchy) (MIT). COSMIC palettes are
from [libcosmic](https://github.com/pop-os/libcosmic) (MPL-2.0). See `NOTICE`.

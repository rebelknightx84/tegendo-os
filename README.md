# tegendo-os

**Fedora COSMIC Atomic + NVIDIA + Steam + Friday + the best of Omarchy, as one signed image.**

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
- **Tegendo OS branding**: the name in About, the boot menu and the console;
  the Tegendo logo and boot splash (including the disk-unlock screen); the
  Tegendo theme and wallpaper by default; fastfetch with the Tegendo logo in
  the first terminal of each boot (`touch ~/.config/tegendo-os/no-welcome` to
  turn it off). Fedora stays underneath (`ID=fedora`), so Fedora tools,
  Flatpak and Distrobox work unchanged.
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
- **NVIDIA, Secure Boot-ready**: the driver's open kernel modules are built
  in CI and signed with your own key; enroll it once with `tos mok enroll`.
- **Gaming**: Steam, ProtonUp-Qt (Proton-GE), Protontricks, MangoHud,
  gamescope and Flatseal install on first boot (`image/flatpaks.txt`), plus
  controller support (`steam-devices`).
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
3. Log in. `tos-setup` runs once on its own (theme, Friday, Flathub), and
   the Flatpak set installs in the background once you're online.
   Check with `tos status`.
4. NVIDIA machines: `tos mok enroll`, reboot, approve the key in the blue
   MOK Manager screen, then turn Secure Boot on in the firmware.
5. `tos signing enforce`, then reboot: from now on this machine only installs
   OS images signed with your key.

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
tos mok [status|enroll]        # Secure Boot key for the NVIDIA driver
tos signing [status|enforce]   # only install OS updates signed with your key
tos friday-log                 # what Friday did
tos-mcp --list-tools           # Friday's tools and their tiers
```

## Changing the OS

Edit the repo, open a PR, merge when CI is green, then `tos update` on each
machine. To add a system package, add a line to `image/packages.txt`
(official Fedora repos only). To give every machine a Flatpak, add it to
`image/flatpaks.txt`.

**One-time setup for NVIDIA signing** (before the first build on main):
run `tools/make-mok-key.sh`, put the private key in the `MOK_PRIVATE_KEY`
repository secret, commit `image/nvidia/tegendo-mok.der`. Builds on main
refuse to publish without it.

## Layout

```
image/Containerfile     the OS: Fedora COSMIC Atomic + build.sh
image/build.sh          installs packages, tools, data, hardening (runs at build time only)
image/packages.txt      system packages, official repos only
image/flatpaks.txt      Flatpaks every machine gets (Steam, Proton tools, ...)
image/nvidia/           NVIDIA: build + sign modules (stage 1), install (stage 2), RPM Fusion repo
image/branding.sh       name (os-release), icon, boot splash + initramfs, fastfetch, welcome
image/system/           firewalld zone, sshd drop-in
src/bin/                tos, tos-theme, tos-mcp, tos-doctor, tos-agent, tos-crash-watch, tos-setup
src/lib/                tos_redact.py (shared secret scrubbing)
src/libexec/tos-helper  the only code Friday can run as root (via polkit)
src/libexec/tos-flatpak-provision  installs image/flatpaks.txt on boot
src/polkit/             password-every-time policy for tos-helper
src/skills/             the tegendo-os skill (teaches agents how this system works)
src/share/cosmic/       COSMIC base palettes (from libcosmic, MPL-2.0)
src/share/branding/     logo + splash + wallpaper sources (SVG), fastfetch logo/config
src/share/themes/       our own themes (tegendo, the default)
vendor/omarchy/         pinned, data-only slice of Omarchy (themes, templates, crash skill)
tools/upstream-sync.sh  the only way upstream content enters this repo
tools/make-mok-key.sh   one-time: your NVIDIA module-signing key
tools/make-cosign-key.sh  one-time: your image-signing key (machines enforce it)
tools/ci-sign.sh        how CI signs images (also used by tests/signing-policy.sh)
image/signing.sh        the image's update-signing policy
tools/render-branding.sh  re-render the branding PNGs after editing the SVGs
tests/                  renderer parity, COSMIC theme parsing, tos-mcp (incl. a real MCP client), Flatpak provisioning
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
2. **Done (v0.3):** Fedora COSMIC Atomic bootc image, built and signed in CI.
3. **Done (v0.4):** NVIDIA in the image (signed with your key), gaming Flatpak set.
   **Done (v0.5):** Tegendo OS branding (name, logo, boot splash, default theme, terminal welcome).
   **Now (v0.6):** signature-enforced updates; rechunked images for smaller updates.
4. **Next:** Friday's Super+Space assistant and proactive watchers.
5. **v2/v3: one-click app menu** (Omarchy-style): a curated catalog of
   Flatpaks and Distrobox recipes for .deb apps, installable with one click.
   Friday installs from the same catalog, so there's one approved list.
6. **Later:** a COSMIC panel applet for Friday; an installer ISO from the same
   image (interactive, never an unattended disk wipe), with known hardware
   fixes applied automatically.

## Credits

Themes, templates and the diagnose-crash skill are from
[Omarchy](https://github.com/basecamp/omarchy) (MIT). COSMIC palettes are
from [libcosmic](https://github.com/pop-os/libcosmic) (MPL-2.0). See `NOTICE`.

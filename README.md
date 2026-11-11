# tegendo-os

**CachyOS + COSMIC + the best of Omarchy, under your control.**

A personal distribution layer. It doesn't fork an OS. It adds a small set of
opinions and tools on top of CachyOS, using the same model as Omarchy, with
three differences:

| | Omarchy | tegendo-os |
|---|---|---|
| Base | Arch, its own pacman repo; replaces `/etc/pacman.conf` | CachyOS repos untouched (preflight refuses to run otherwise) |
| Desktop | Hyprland + Quickshell | COSMIC (floating by default, tiling per workspace) |
| Updates | pushed from Omarchy's repo | nothing upstream reaches the machine unless you sync, review and commit it |
| AI agents | launched with `--yolo` / auto-approve | ask before every action; diagnostics redacted and confirmed before sending |

## What you get

- **Omarchy's 22 themes**: `tos theme set tokyo-night` recolors COSMIC
  (accent, background, wallpaper), Ghostty and btop automatically, and
  generates matching config files for Kitty, Alacritty, Foot, Helix,
  Neovim, VS Code and more in `~/.local/state/tegendo-os/current/theme/`,
  ready to point those apps at.
- **AI troubleshooting**: `tos doctor "why does wifi drop?"` collects read-only
  diagnostics, scrubs secrets, shows you what it'll send, then hands off to
  Claude Code, Codex, or a local Ollama model.
- **Friday (tos-mcp)**: Claude, or any MCP client, connected to the OS.
  Reading is automatic and redacted; changing your settings needs a click;
  system changes need a click plus your password and run between snapshots.
  There's no shell tool. See [docs/FRIDAY.md](docs/FRIDAY.md).
- **Crash watcher**: when one of your apps dumps core, a notification offers
  "Diagnose with AI" (using Omarchy's diagnose-crash method).
- **Baseline hardening**: ufw (deny inbound, allow Tailscale), key-only SSH,
  snap-pac snapshots around every update, LUKS / Secure Boot / NVIDIA checks.
- **Everything in Ansible**: rebuild a machine from this repo.

## Install

On a fresh **CachyOS** install (pick COSMIC, Btrfs + Snapper, and encryption
in the installer):

```bash
git clone <your-repo-url> ~/tegendo-os && cd ~/tegendo-os
./bootstrap.sh --check     # dry run: every change shown, nothing applied
./bootstrap.sh             # apply
```

Knobs live in `ansible/group_vars/all.yml` (agent choice, default theme,
firewall, opt-in bootloader fix).

## Commands

```
tos theme list | current | set <name>
tos doctor [question]          tos doctor crash <pid>
tos agent "prompt"
tos update                     # paru -Syu (snap-pac snapshots around it)
tos apply                      # re-run Ansible from this repo
tos status
tos friday-log                 # what Friday did
tos undo <snapshot>            # revert a Friday change (only you can)
tos-mcp --list-tools           # Friday's tools and their tiers
```

## Layout

```
bootstrap.sh            entry point on a fresh CachyOS
ansible/                roles: preflight, base, security, nvidia, desktop, themes, ai
src/bin/                tos, tos-theme, tos-mcp (Python), tos-doctor, tos-agent, tos-crash-watch
src/lib/                tos_redact.py (shared secret scrubbing)
src/libexec/tos-helper  the only code Friday can run as root (via polkit)
src/polkit/             password-every-time policy for tos-helper
src/skills/             the tegendo-os skill (teaches agents how this system works)
src/share/cosmic/       COSMIC base palettes (from libcosmic, MPL-2.0)
vendor/omarchy/         pinned, data-only slice of Omarchy (themes, templates, crash skill)
tools/upstream-sync.sh  the only way upstream content enters this repo
tests/                  renderer parity, COSMIC theme parsing, tos-mcp (incl. a real MCP client)
.github/workflows/ci.yml  runs the tests that execute upstream code (never on your desktop)
```

## Docs

- [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md): how the pieces fit and the trust model
- [docs/UPSTREAM.md](docs/UPSTREAM.md): pulling new Omarchy themes safely
- [docs/FRIDAY.md](docs/FRIDAY.md): tos-mcp, permission tiers, honest limits
- [docs/AI.md](docs/AI.md): agents, privacy, local models
- [docs/SECURITY.md](docs/SECURITY.md): what's hardened, what's manual, what to watch

## Roadmap

1. **Done (v0.1):** Ansible layer on stock CachyOS.
2. **Now (v0.2):** Friday: tos-mcp (done) → Super+Space assistant → proactive
   watchers → COSMIC panel applet.
3. **Next:** a signed pacman repo with `tegendo-os-*` meta-packages, so updates
   arrive via `pacman -Syu` instead of re-running Ansible.
4. **Later:** an archiso ISO based on CachyOS's profile, with this preinstalled
   and known hardware fixes (like hybrid-GPU boot parameters) applied automatically.

## Credits

Themes, templates and the diagnose-crash skill are from
[Omarchy](https://github.com/basecamp/omarchy) (MIT). COSMIC palettes are
from [libcosmic](https://github.com/pop-os/libcosmic) (MPL-2.0). See `NOTICE`.

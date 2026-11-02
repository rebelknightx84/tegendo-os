# Architecture

## Layers

```
┌───────────────────────────────────────────────────────────────┐
│ tegendo-os layer   tos tools · themes · AI doctor · hardening │  ← this repo
├───────────────────────────────────────────────────────────────┤
│ COSMIC desktop     cosmic-comp, cosmic-settings, cosmic-bg    │  ← Arch/CachyOS packages
├───────────────────────────────────────────────────────────────┤
│ CachyOS            optimized kernels & packages, chwd, Limine │  ← CachyOS repos
└───────────────────────────────────────────────────────────────┘
          Omarchy contributes DATA ONLY → vendor/omarchy/ (pinned)
```

## Trust model

The design rule: **no third-party code reaches your desktop without passing
through a commit you made.**

| Source | What we take | How it's trusted |
|---|---|---|
| CachyOS / Arch repos | all packages | signed repos, unchanged `pacman.conf` |
| Omarchy | themes, `.tpl` templates, diagnose-crash skill (markdown) | pinned to a full commit SHA, allowlisted paths, no executables/symlinks, reviewed in a PR, parity-tested in CI |
| libcosmic | two palette files (data) | copied once, versioned in git |
| AUR | only what you choose | `paru` shows each PKGBUILD diff before building |

Omarchy's theme engine is shell scripts. Rather than run them, `tos-theme`
re-implements the color resolver and template renderer in Python, and
`tests/theme-parity.sh` proves the output is byte-identical to upstream's for
every theme. That test runs in CI, which is the only place Omarchy code runs.

## Theme pipeline

```
tos theme set tokyo-night
  1. stage   /usr/share/tegendo-os/themes/tokyo-night   (+ ~/.config/tegendo-os/themes/ overlay)
  2. resolve colors.toml → full palette (aliases, derived shades, light/dark)
  3. render  templates: ~/.config/tegendo-os/themed → themed-extra → vendored Omarchy
  4. bridge  cosmic-theme.ron (COSMIC ThemeBuilder) + wallpaper entry
  5. swap    atomically into ~/.local/state/tegendo-os/current/theme
  6. apply   cosmic-settings appearance import · cosmic-bg config · reload ghostty/kitty
             · run ~/.config/tegendo-os/hooks/theme-set if present
```

Apps point at `~/.local/state/tegendo-os/current/theme/<file>` once (the
desktop role does this for Ghostty and btop), so later theme changes need no
config edits.

**COSMIC mapping:** `background` → bg, `foreground` → text tint, `accent` →
accent and window hint, `green/yellow/red` → success/warning/destructive.
Light or dark comes from the theme's `mode`, or from background luminance.

## AI pipeline

```
crash (systemd-coredump) ──► tos-crash-watch ──► notification ──► "Diagnose"
                                                                     │
tos doctor [question] ───────────────────────────────────────────────┤
                                                                     ▼
           read-only collection → redaction → 0600 report → you confirm
                                                                     ▼
           tos-agent: claude / codex (ask per action) · ollama (advice only)
           + skills: tegendo-os (how this box is built) + diagnose-crash
```

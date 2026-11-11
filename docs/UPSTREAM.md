# Pulling from Omarchy

Omarchy can never update your machine on its own. New themes arrive only
like this:

```bash
tools/upstream-sync.sh status            # what's pinned vs newest upstream tags
tools/upstream-sync.sh diff v4.0.7       # what would change (allowlisted paths only)
git switch -c sync/omarchy-v4.0.7
tools/upstream-sync.sh apply v4.0.7      # stage into vendor/omarchy/, validate
git diff -- vendor/omarchy               # read it
git add vendor/omarchy && git commit -m "Sync Omarchy themes v4.0.7"
git push -u origin HEAD                  # open a PR; CI must be green
```

Merging to main triggers a new image; then `tos update` on each machine.

## What `apply` enforces

- Only allowlisted paths: `themes/`, `default/themed/`,
  `default/agents/skills/diagnose-crash/SKILL.md`, `LICENSE`.
- No symlinks, no executable bits, no unexpected file types, nothing over 20 MB.
- `.lua` and `.json` payloads (Neovim / VS Code theme files) are listed for
  you to read, since those apps load them.
- The lock records the full commit SHA, so what you reviewed is what stays pinned.
- No Omarchy code runs. CI runs the parity test, which executes Omarchy's
  renderer in a throwaway HOME, and checks vendored files match the pinned commit.

## Prefer stable tags

Pin release tags (`v4.0.6`), not release candidates or `master`. You don't
need Omarchy's newest desktop features, only its themes.

## Changing the allowlist

Edit `ALLOW=(...)` in `tools/upstream-sync.sh`. Every new path is a new trust
decision, so prefer data (themes, templates, markdown) over scripts.

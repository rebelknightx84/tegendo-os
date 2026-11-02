#!/usr/bin/env bash
# =============================================================================
# theme-parity.sh — prove tos-theme renders exactly what Omarchy renders.
#
# For every vendored theme: compares resolved colors (omarchy-theme-color
# --all) and every rendered template (omarchy-theme-set-templates) between
# upstream's bash and our Python, byte for byte.
#
# Upstream code runs ONLY here, in a throwaway HOME, never on the desktop.
#
#   OMARCHY_SRC=<omarchy checkout at the pinned commit>  (required)
#   VENDOR_DIR=<vendor/omarchy to test>                  (default: repo's)
# =============================================================================
set -euo pipefail

ROOT=$(cd "$(dirname "$0")/.." && pwd)
SRC=${OMARCHY_SRC:?set OMARCHY_SRC to an Omarchy checkout at the pinned commit}
VENDOR=${VENDOR_DIR:-$ROOT/vendor/omarchy}
TOS="$ROOT/src/bin/tos-theme"

work=$(mktemp -d); trap 'rm -rf "$work"' EXIT
mkdir -p "$work/bin"
# Upstream calls these at the end of rendering; they touch the live desktop.
printf '#!/bin/sh\nexit 0\n' >"$work/bin/omarchy-theme-set-glass"
chmod +x "$work/bin/omarchy-theme-set-glass"

pass=0 fail=0
for theme in "$VENDOR"/themes/*/; do
  name=$(basename "$theme")
  [[ -f $theme/colors.toml ]] || continue

  # 1. color resolution
  if ! diff <(bash "$SRC/bin/omarchy-theme-color" --file "$theme/colors.toml" --all 2>/dev/null) \
            <(python3 "$TOS" colors --file "$theme/colors.toml" --all 2>/dev/null) >"$work/colors.diff"; then
    echo "FAIL colors  $name"; sed 's/^/    /' "$work/colors.diff" | head -10; fail=$((fail + 1)); continue
  fi

  # 2. template rendering
  home="$work/home-$name"
  up="$home/.local/state/omarchy/current/next-theme"
  ours="$work/ours-$name"
  mkdir -p "$up" "$ours"
  cp -R "$theme." "$up/"; cp -R "$theme." "$ours/"

  HOME="$home" OMARCHY_PATH="$SRC" PATH="$work/bin:$SRC/bin:$PATH" \
    bash "$SRC/bin/omarchy-theme-set-templates" 2>/dev/null
  python3 "$TOS" render --colors "$ours/colors.toml" --out "$ours" "$VENDOR/themed"

  if diff -r "$up" "$ours" >"$work/render.diff"; then
    pass=$((pass + 1))
  else
    echo "FAIL render  $name"; sed 's/^/    /' "$work/render.diff" | head -15; fail=$((fail + 1))
  fi
done

echo "theme parity: $pass passed, $fail failed"
(( fail == 0 && pass > 0 ))

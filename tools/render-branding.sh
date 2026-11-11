#!/usr/bin/env bash
# Re-render the Tegendo OS branding PNGs from their SVG sources.
# Needs rsvg-convert (librsvg) and the Inter font. Run from the repo root
# after editing anything in src/share/branding/*.svg, then commit the PNGs.
set -euo pipefail
cd src/share/branding
rsvg-convert watermark.svg -o plymouth/watermark.png                          # boot splash
rsvg-convert wallpaper.svg -o ../themes/tegendo/backgrounds/0-tegendo.png      # default wallpaper
echo "rendered: plymouth/watermark.png, themes/tegendo/backgrounds/0-tegendo.png"

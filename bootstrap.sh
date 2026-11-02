#!/usr/bin/env bash
# =============================================================================
# bootstrap.sh — turn a fresh CachyOS (COSMIC edition) install into tegendo-os.
#
#   git clone <your repo> ~/tegendo-os && cd ~/tegendo-os
#   ./bootstrap.sh --check     # dry run: shows every change, makes none
#   ./bootstrap.sh             # apply
#   ./bootstrap.sh --tags themes,ai   # just some roles
#
# Run as your normal user. sudo is used only by tasks that need it.
# =============================================================================
set -euo pipefail

cd "$(dirname "$0")"

[[ $EUID -ne 0 ]] || { echo "Run as your normal user, not root."; exit 1; }
grep -q '^ID=cachyos' /etc/os-release 2>/dev/null ||
  { echo "This is for CachyOS. Detected: $(. /etc/os-release && echo "$ID")"; exit 1; }

need=()
command -v ansible-playbook >/dev/null || need+=(ansible)
command -v git >/dev/null || need+=(git)
if ((${#need[@]})); then
  echo "Installing: ${need[*]}"
  sudo pacman -S --needed --noconfirm "${need[@]}"
fi

if ! ansible-galaxy collection list community.general 2>/dev/null | grep -q community.general; then
  ansible-galaxy collection install -r ansible/requirements.yml
fi

extra=()
for a in "$@"; do
  case "$a" in
    --check) extra+=(--check --diff) ;;
    *) extra+=("$a") ;;
  esac
done

cd ansible
exec ansible-playbook site.yml --ask-become-pass "${extra[@]}"

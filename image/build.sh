#!/usr/bin/bash
# =============================================================================
# build.sh — runs once inside the image build (see Containerfile). Installs
# packages from official Fedora repos, the tegendo-os tools and data, and
# system hardening. Never runs on a live machine.
#
# Atomic layout rules this follows:
#   /usr  = image content (read-only on the machine) → all our files go here
#   /etc  = defaults merged with the machine's own changes
#   /usr/local and /opt are machine state on Atomic, so nothing goes there
# =============================================================================
set -euxo pipefail

CTX=/ctx
: "${TOS_VERSION:?}" "${FEDORA_VERSION:?}"

# ---- packages (official repos only) -------------------------------------------
mapfile -t pkgs < <(sed -e 's/#.*//' -e 's/[[:space:]]*$//' "$CTX/image/packages.txt" | grep -v '^[[:space:]]*$')
dnf -y install --setopt=install_weak_deps=False "${pkgs[@]}"
dnf clean all

# ---- NVIDIA (signed modules from the nvidia-kmod stage + matching userspace) ------
# The only step that touches RPM Fusion; see image/nvidia/install.sh.
"$CTX/image/nvidia/install.sh" /nvidia

# ---- tegendo-os tools -------------------------------------------------------------
install -Dm755 -t /usr/bin \
  "$CTX/src/bin/tos" "$CTX/src/bin/tos-theme" "$CTX/src/bin/tos-mcp" "$CTX/src/bin/tos-doctor" \
  "$CTX/src/bin/tos-agent" "$CTX/src/bin/tos-crash-watch" "$CTX/src/bin/tos-setup"
install -Dm644 "$CTX/src/lib/tos_redact.py" /usr/lib/tegendo-os/tos_redact.py
install -Dm755 "$CTX/src/libexec/tos-helper" /usr/lib/tegendo-os/tos-helper
install -Dm755 "$CTX/src/libexec/tos-flatpak-provision" /usr/lib/tegendo-os/tos-flatpak-provision
install -Dm644 -t /usr/share/polkit-1/actions "$CTX"/src/polkit/*.policy

# ---- shared data: themes (Omarchy, pinned), palettes, skills ----------------------
share=/usr/share/tegendo-os
install -d "$share"
cp -r "$CTX/vendor/omarchy/themes" "$CTX/vendor/omarchy/themed" "$share/"
cp -r "$CTX/src/share/themes/." "$share/themes/"   # our own themes (tegendo = the default)
cp -r "$CTX/src/share/cosmic" "$share/cosmic"
install -d "$share/skills"
cp -r "$CTX/vendor/omarchy/skills/." "$CTX/src/skills/." "$share/skills/"
install -m644 "$CTX/vendor/omarchy/UPSTREAM.lock" "$share/UPSTREAM.lock"
install -m644 "$CTX/vendor/omarchy/LICENSE" "$share/OMARCHY-LICENSE"
install -m644 "$CTX/NOTICE" "$share/NOTICE"
install -m644 "$CTX/image/flatpaks.txt" "$share/flatpaks.txt"
echo "$TOS_VERSION" >"$share/VERSION"
find "$share" -type d -exec chmod 755 {} + && find "$share" -type f -exec chmod 644 {} +

# ---- the image's Flatpak set (Steam, Proton tools, ...) -------------------------------
# Installed system-wide from Flathub on first boot, and again whenever
# image/flatpaks.txt changes. Apps you remove stay removed until the list changes.
install -Dm644 -t /usr/lib/systemd/system "$CTX/src/systemd/tos-flatpak-provision.service"
systemctl enable tos-flatpak-provision.service

# ---- per-user services --------------------------------------------------------------
install -Dm644 -t /usr/lib/systemd/user "$CTX/src/systemd/tos-crash-watch.service"
install -Dm644 /dev/stdin /usr/lib/systemd/user-preset/90-tegendo-os.preset <<'EOF'
enable tos-crash-watch.service
EOF
# First-login setup runs inside the graphical session (needs the display).
install -Dm644 "$CTX/src/autostart/tos-setup.desktop" /etc/xdg/autostart/tos-setup.desktop

# ---- hardening ----------------------------------------------------------------------
# Fedora Workstation's default zone allows inbound 1025-65535. Ours drops all
# inbound except DHCPv6 replies; anything on the tailnet is trusted.
install -Dm644 "$CTX/image/system/firewalld-tegendo.xml" /etc/firewalld/zones/tegendo.xml
firewall-offline-cmd --set-default-zone=tegendo
firewall-offline-cmd --zone=trusted --add-interface=tailscale0
systemctl enable firewalld.service

# SSH stays off unless enabled by hand; if it ever is, keys only.
install -Dm644 "$CTX/image/system/sshd-tegendo.conf" /etc/ssh/sshd_config.d/10-tegendo-os.conf

# Tailscale daemon available but idle until `sudo tailscale up`.
systemctl enable tailscaled.service

# Atomic: automatic staged updates of the base OS are off; `tos update` is
# explicit, so a broken upstream build never surprises you mid-week.
systemctl disable bootc-fetch-apply-updates.timer 2>/dev/null || true

# ---- branding: name, logo, boot splash, fastfetch, welcome --------------------------
# Last, because it rebuilds the initramfs from everything installed above.
"$CTX/image/branding.sh" "$CTX" "$TOS_VERSION"

# shellcheck shell=bash
# Shared helpers for the NVIDIA build scripts (sourced, never run).

die() { echo "nvidia: $*" >&2; exit 1; }

# Adds the build-time-only RPM Fusion repo (NVIDIA packages only).
# RPM Fusion's key comes from Fedora's distribution-gpg-keys package.
enable_rpmfusion() {
  local here=$1 rel
  rel=$(rpm -E %fedora)
  dnf -y install --setopt=install_weak_deps=False distribution-gpg-keys
  [[ -f /usr/share/distribution-gpg-keys/rpmfusion/RPM-GPG-KEY-rpmfusion-nonfree-fedora-$rel ]] ||
    die "Fedora's distribution-gpg-keys has no RPM Fusion nonfree key for Fedora $rel yet; can't verify RPM Fusion packages."
  install -m644 "$here/rpmfusion-nvidia.repo" /etc/yum.repos.d/tos-rpmfusion-nvidia.repo
}

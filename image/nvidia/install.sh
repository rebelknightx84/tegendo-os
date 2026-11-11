#!/usr/bin/bash
# =============================================================================
# install.sh — runs in the final image build (called by build.sh). Installs the
# signed modules built by build-kmod.sh plus the matching NVIDIA userspace from
# RPM Fusion, then removes the repo again. Usage: install.sh <dir from build-kmod.sh>
# =============================================================================
set -euo pipefail

here=$(dirname "$(readlink -f "$0")")
# shellcheck source=image/nvidia/common.sh
source "$here/common.sh"

in=${1:?usage: install.sh <kmod dir>}
if [[ ! -f $in/NVIDIA_VERSION ]]; then
  echo "nvidia: no driver built (WITH_NVIDIA=0), skipping"
  exit 0
fi
ver=$(<"$in/NVIDIA_VERSION")
mapfile -t kmods < <(find "$in" -maxdepth 1 -name 'kmod-nvidia-*.rpm')
(( ${#kmods[@]} == 1 )) || die "expected one kmod-nvidia RPM in $in"

# The modules must be for this image's kernel (both stages start from the same base).
kver=$(ls /usr/lib/modules)
[[ $(basename "${kmods[0]}") == kmod-nvidia-"$kver"-* ]] || die "$(basename "${kmods[0]}") doesn't match kernel $kver"

enable_rpmfusion "$here"
# Userspace pinned to the module's version. No akmods: nothing compiles on the machine.
#   xorg-x11-drv-nvidia        driver libraries (Wayland/GBM, Vulkan, OpenGL)
#   xorg-x11-drv-nvidia-cuda   nvidia-smi + CUDA/NVENC libraries (local AI, encoding)
#   xorg-x11-drv-nvidia-power  suspend/resume/hibernate helpers
dnf -y install --setopt=install_weak_deps=False \
  "${kmods[0]}" \
  "xorg-x11-drv-nvidia-$ver" "xorg-x11-drv-nvidia-cuda-$ver" "xorg-x11-drv-nvidia-power-$ver"
disable_rpmfusion
[[ -f /etc/nvidia/kernel.conf ]] && sed -i 's/^MODULE_VARIANT=.*/MODULE_VARIANT=kernel-open/' /etc/nvidia/kernel.conf
rpm -q akmods akmod-nvidia >/dev/null 2>&1 && die "akmods ended up in the image; it must not"
dnf clean all

systemctl enable nvidia-suspend.service nvidia-resume.service nvidia-hibernate.service

# Keep nouveau out of the way (in the initramfs and after). Applied by bootc on switch/upgrade.
install -Dm644 /dev/stdin /usr/lib/bootc/kargs.d/10-tegendo-nvidia.toml <<'EOF'
kargs = ["rd.driver.blacklist=nouveau", "modprobe.blacklist=nouveau", "nvidia-drm.modeset=1"]
match-architectures = ["x86_64"]
EOF

# Public cert for `tos mok enroll` (only shipped when signed with your key).
if [[ -f $in/tegendo-mok.der ]]; then
  install -Dm644 "$in/tegendo-mok.der" /usr/share/tegendo-os/mok/tegendo-mok.der
fi
install -Dm644 "$in/SIGNED_WITH" /usr/share/tegendo-os/mok/SIGNED_WITH
echo "nvidia: installed driver $ver for $kver (modules signed with: $(<"$in/SIGNED_WITH"))"

#!/usr/bin/bash
# =============================================================================
# build-kmod.sh — runs in the throwaway "nvidia-kmod" build stage (see
# Containerfile). Builds NVIDIA's open kernel modules from RPM Fusion's
# akmod-nvidia for the exact kernel in the base image, signs them with your
# Machine Owner Key (MOK), verifies the signature, and leaves the result in /out:
#
#   /out/kmod-nvidia-*.rpm   the signed modules, as an RPM
#   /out/NVIDIA_VERSION      driver version, so install.sh pins userspace to it
#   /out/SIGNED_WITH         "mok" (your key) or "throwaway" (dev/PR builds)
#   /out/tegendo-mok.der     public cert to enroll (only when signed with your key)
#
# The private key arrives as a podman build secret (never in a layer), is
# copied where akmods looks for it for the length of this one RUN, and is
# deleted before the RUN ends. Nothing from this stage is published except
# the files in /out.
# =============================================================================
set -euo pipefail

here=$(dirname "$(readlink -f "$0")")
# shellcheck source=image/nvidia/common.sh
source "$here/common.sh"

out=/out
install -d "$out"
: "${WITH_NVIDIA:=1}" "${REQUIRE_MOK_KEY:=0}"
if [[ $WITH_NVIDIA != 1 ]]; then
  echo "nvidia: WITH_NVIDIA=$WITH_NVIDIA, skipping"
  exit 0
fi

key_secret=/run/secrets/mok_key
repo_cert=$here/tegendo-mok.der
pki=/etc/pki/akmods

# Wipe the private key however this script ends.
cleanup() { rm -rf "$pki/private" /tmp/kmod-check; }
trap cleanup EXIT

# ---- the kernel we build for: the one in the base image -------------------------
mapfile -t kernels < <(ls /usr/lib/modules)
(( ${#kernels[@]} == 1 )) || die "expected one kernel in the base image, found: ${kernels[*]}"
kver=${kernels[0]}
echo "nvidia: building for kernel $kver"

# ---- packages ------------------------------------------------------------------------
enable_rpmfusion "$here"
# Open kernel modules (MIT/GPL), the ones NVIDIA recommends for Turing and newer.
echo '%_with_kmod_nvidia_open 1' >/etc/rpm/macros.nvidia-kmod
# Build tools first, with their install scripts (akmods' creates the 'akmods'
# build user). Then akmod-nvidia with scripts off: its own script tries to
# build right away as root, which akmods refuses and dnf counts as a failed
# install. We run the build ourselves below, for the right kernel.
dnf -y install --setopt=install_weak_deps=False "kernel-devel-$kver" akmods openssl cpio
dnf -y install --setopt=install_weak_deps=False --setopt=tsflags=noscripts akmod-nvidia
# Container builds can leave these with odd permissions, which breaks rpmbuild.
chmod 1777 /tmp /var/tmp
mkdir -p /var/lib/alternatives
# Newer RPM Fusion packages also read this switch; set it too if present.
[[ -f /etc/nvidia/kernel.conf ]] && sed -i 's/^MODULE_VARIANT=.*/MODULE_VARIANT=kernel-open/' /etc/nvidia/kernel.conf

# ---- signing key ---------------------------------------------------------------------
install -d -m755 "$pki/certs"
install -d -m750 "$pki/private"
if [[ -s $key_secret ]]; then
  [[ -f $repo_cert ]] || die "a MOK private key was provided but image/nvidia/tegendo-mok.der is missing; run tools/make-mok-key.sh"
  # The key must belong to the committed cert, or every machine would refuse the modules.
  [[ "$(openssl pkey -in "$key_secret" -pubout)" == "$(openssl x509 -inform DER -in "$repo_cert" -noout -pubkey)" ]] ||
    die "the MOK private key doesn't match image/nvidia/tegendo-mok.der"
  install -m640 "$key_secret" "$pki/private/private_key.priv"
  install -m644 "$repo_cert" "$pki/certs/public_key.der"
  signed_with=mok
else
  [[ $REQUIRE_MOK_KEY == 1 ]] && die "REQUIRE_MOK_KEY=1 but no MOK key was provided (build secret 'mok_key')"
  echo "nvidia: WARNING: no MOK key; signing with a throwaway key. This image's NVIDIA modules won't load with Secure Boot on. Fine for PR/dev builds, never publish it."
  openssl req -new -x509 -newkey rsa:2048 -nodes -sha256 -days 30 \
    -subj "/CN=tegendo-os throwaway build key" \
    -keyout "$pki/private/private_key.priv" -outform DER -out "$pki/certs/public_key.der" 2>/dev/null
  signed_with=throwaway
fi
chgrp -R akmods "$pki" 2>/dev/null || true

# ---- build ---------------------------------------------------------------------------
if ! akmods --force --kernels "$kver" --kmod nvidia; then
  cat /var/cache/akmods/nvidia/*.failed.log 2>/dev/null || true
  die "akmods failed to build the NVIDIA modules for $kver"
fi
mapfile -t rpms < <(find /var/cache/akmods/nvidia -name "kmod-nvidia-${kver}-*.rpm")
(( ${#rpms[@]} == 1 )) || die "expected one kmod-nvidia RPM for $kver, found ${#rpms[@]}"

# ---- verify: open modules, signed by the expected key ------------------------------------
expected_signer=$(openssl x509 -inform DER -in "$pki/certs/public_key.der" -noout -subject -nameopt multiline |
  sed -n 's/^ *commonName *= *//p')
mkdir -p /tmp/kmod-check
(cd /tmp/kmod-check && rpm2cpio "${rpms[0]}" | cpio -idm --quiet)
mapfile -t mods < <(find /tmp/kmod-check -name 'nvidia*.ko*')
(( ${#mods[@]} > 0 )) || die "no nvidia modules inside ${rpms[0]}"
for m in "${mods[@]}"; do
  signer=$(modinfo -F signer "$m")
  license=$(modinfo -F license "$m")
  [[ $signer == "$expected_signer" ]] || die "$(basename "$m") signed by '$signer', expected '$expected_signer'"
  [[ $license == "Dual MIT/GPL" ]] || die "$(basename "$m") has license '$license'; expected the open modules"
  echo "nvidia: ok $(basename "$m") (signer: $signer, $license)"
done

# ---- hand off --------------------------------------------------------------------------
cp "${rpms[0]}" "$out/"
rpm -q --qf '%{VERSION}\n' akmod-nvidia >"$out/NVIDIA_VERSION"
echo "$signed_with" >"$out/SIGNED_WITH"
[[ $signed_with == mok ]] && cp "$repo_cert" "$out/tegendo-mok.der"
echo "nvidia: built $(basename "${rpms[0]}") (driver $(cat "$out/NVIDIA_VERSION"), signed with: $signed_with)"

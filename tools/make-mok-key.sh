#!/usr/bin/env bash
# =============================================================================
# make-mok-key.sh — one-time: create your Machine Owner Key (MOK) for signing
# the NVIDIA kernel modules. Run on your own machine (macOS or Linux), from
# the repo root:
#
#     tools/make-mok-key.sh
#
# Writes:
#   image/nvidia/tegendo-mok.der   public cert: commit it (machines enroll it)
#   ~/tegendo-mok.key              PRIVATE key: goes into a GitHub secret, then
#                                  your password manager, then gets deleted here
#
# Whoever holds the private key can get kernel code trusted by every machine
# that enrolled the cert. Treat it like a root password.
# =============================================================================
set -euo pipefail

cert=image/nvidia/tegendo-mok.der
key=${1:-$HOME/tegendo-mok.key}
[[ -d image/nvidia ]] || { echo "run from the tegendo-os repo root"; exit 1; }
[[ ! -e $cert ]] || { echo "$cert already exists; rotating a key means re-enrolling every machine. Remove it first if you mean it."; exit 1; }
[[ ! -e $key ]] || { echo "$key already exists"; exit 1; }

cfg=$(mktemp)
trap 'rm -f "$cfg"' EXIT
# Same shape as the kernel's own module-signing keys (and akmods' kmodgenca).
cat >"$cfg" <<'EOF'
[ req ]
default_bits = 4096
distinguished_name = dn
prompt = no
x509_extensions = ext
[ dn ]
CN = tegendo-os kernel module signing
O = tegendo-os
[ ext ]
basicConstraints = critical,CA:FALSE
keyUsage = digitalSignature
subjectKeyIdentifier = hash
authorityKeyIdentifier = keyid
EOF

umask 077
openssl req -new -x509 -nodes -sha256 -days 36500 -newkey rsa:4096 \
  -config "$cfg" -keyout "$key" -outform DER -out "$cert"
chmod 644 "$cert"

cat <<EOF

Created:
  $cert   (public; commit it)
  $key    (PRIVATE)

Fingerprint (tos mok enroll shows the same one on the machine):
$(openssl x509 -inform DER -in "$cert" -noout -fingerprint -sha256)

Next:
  1. gh secret set MOK_PRIVATE_KEY < "$key"
  2. Save $key in your password manager, then delete it:  rm -P "$key"   (macOS)
  3. git add $cert && git commit -m "Add MOK cert for NVIDIA module signing"
EOF

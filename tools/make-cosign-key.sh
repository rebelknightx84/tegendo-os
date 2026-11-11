#!/usr/bin/env bash
# =============================================================================
# make-cosign-key.sh — one-time: create the image-signing key. Run on your own
# machine (macOS or Linux) from the repo root:
#
#     tools/make-cosign-key.sh
#
# Writes:
#   image/signing/cosign.pub   public key: commit it (machines verify updates with it)
#   ~/tegendo-cosign.key       PRIVATE key (EC P-256, PEM): goes into the
#                              COSIGN_PRIVATE_KEY Actions secret, then gets deleted
#
# Plain openssl on purpose: no cosign install needed here. CI converts the key
# with `cosign import-key-pair` (tools/ci-sign.sh). Whoever holds the private
# key can sign images your machines will install. Treat it like a root password.
# =============================================================================
set -euo pipefail

pub=image/signing/cosign.pub
key=${1:-$HOME/tegendo-cosign.key}
[[ -d image ]] || { echo "run from the tegendo-os repo root"; exit 1; }
[[ ! -e $pub ]] || { echo "$pub already exists; rotating means shipping both keys for one release (see docs/SECURITY.md). Remove it first if you mean it."; exit 1; }
[[ ! -e $key ]] || { echo "$key already exists"; exit 1; }

mkdir -p image/signing
umask 077
openssl genpkey -algorithm EC -pkeyopt ec_paramgen_curve:P-256 -out "$key"
umask 022
openssl pkey -in "$key" -pubout -out "$pub"

cat <<EOF

Created:
  $pub   (public; commit it)
  $key   (PRIVATE)

Next:
  1. GitHub: repo → Settings → Secrets and variables → Actions → New secret
     COSIGN_PRIVATE_KEY = contents of $key   (pbcopy < "$key" on macOS)
  2. Delete it here:  rm -P "$key"   (macOS)  /  shred -u "$key"   (Linux)
  3. git add $pub && git commit -m "Add image signing public key"
EOF

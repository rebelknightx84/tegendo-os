#!/usr/bin/env bash
# =============================================================================
# ci-sign.sh — sign an image with the cosign key, in the format bootc/podman
# verify (a ".sig" tag next to the image, which containers/image reads via
# use-sigstore-attachments). Used by image.yml and tests/signing-policy.sh.
#
#   COSIGN_PRIVATE_KEY   PEM EC private key (from tools/make-cosign-key.sh)
#   ci-sign.sh <image@digest> [extra cosign flags, e.g. --allow-insecure-registry]
#
# The PEM key is converted to cosign's format in a private temp dir with a
# random one-time password, and both are wiped when this exits.
# =============================================================================
set -euo pipefail

ref=${1:?image@digest}
shift
[[ $ref == *@sha256:* ]] || { echo "ci-sign: sign by digest, not tag ($ref)" >&2; exit 1; }
[[ -n ${COSIGN_PRIVATE_KEY:-} ]] || { echo "ci-sign: COSIGN_PRIVATE_KEY is empty" >&2; exit 1; }

work=$(umask 077; mktemp -d)
trap 'rm -rf "$work"' EXIT
(umask 077; printf '%s\n' "$COSIGN_PRIVATE_KEY" >"$work/key.pem")
COSIGN_PASSWORD=$(head -c 24 /dev/urandom | base64)
export COSIGN_PASSWORD
(cd "$work" && cosign import-key-pair --key key.pem --output-key-prefix tos >/dev/null)
rm -f "$work/key.pem"

# Legacy signature format on purpose: containers/image (bootc, podman) reads
# ".sig" attachments, not the newer bundle/referrers format.
cosign sign --yes --key "$work/tos.key" \
  --new-bundle-format=false --use-signing-config=false \
  "$@" "$ref"
echo "ci-sign: signed $ref"

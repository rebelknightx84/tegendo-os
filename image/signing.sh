#!/usr/bin/bash
# =============================================================================
# signing.sh — make machines verify updates (called by build.sh; also used by
# tests/signing-policy.sh against a scratch root).
#
# Installs:
#   /etc/pki/containers/tegendo-os.pub      the cosign public key (image/signing/cosign.pub)
#   /etc/containers/registries.d/…          find cosign signatures on the registry
#   /etc/containers/policy.json             Fedora's default policy + one rule:
#                                           <image repo> must be signed by that key
#
# The rule only bites once the machine's origin requires it: `tos signing
# enforce` (= bootc switch --enforce-container-sigpolicy). Everything else
# keeps Fedora's default policy.
#
# Usage: signing.sh <repo root> <image repo, e.g. ghcr.io/owner/tegendo-os> [dest root]
# =============================================================================
set -euo pipefail

ctx=${1:?repo root}
repo=${2:?image repo}
root=${3:-}
pub_src=$ctx/image/signing/cosign.pub
[[ -s $pub_src ]] || { echo "signing: $pub_src is missing; run tools/make-cosign-key.sh" >&2; exit 1; }
grep -q 'BEGIN PUBLIC KEY' "$pub_src" || { echo "signing: $pub_src isn't a PEM public key" >&2; exit 1; }
[[ $repo =~ ^[a-z0-9.-]+(/[a-z0-9._-]+)+$ ]] || { echo "signing: bad image repo '$repo'" >&2; exit 1; }

keypath=/etc/pki/containers/tegendo-os.pub
install -Dm644 "$pub_src" "$root$keypath"

install -Dm644 /dev/stdin "$root/etc/containers/registries.d/tegendo-os.yaml" <<EOF
# Tegendo OS images: cosign signatures are stored next to the image on the registry.
docker:
  $repo:
    use-sigstore-attachments: true
EOF

base=$root/usr/share/containers/policy.json
[[ -f $base ]] || base=/usr/share/containers/policy.json
jq --arg repo "$repo" --arg key "$keypath" '
  .transports.docker[$repo] = [{
    "type": "sigstoreSigned",
    "keyPath": $key,
    "signedIdentity": {"type": "matchRepository"}
  }]' "$base" >"$root/etc/containers/policy.json.new"
mv "$root/etc/containers/policy.json.new" "$root/etc/containers/policy.json"
chmod 644 "$root/etc/containers/policy.json"
echo "signing: $repo requires the key in $keypath (enforced after: tos signing enforce)"

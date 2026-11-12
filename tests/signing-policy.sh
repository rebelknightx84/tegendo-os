#!/usr/bin/env bash
# =============================================================================
# End-to-end test of update signing, with the real scripts and a throwaway key:
#   tools/ci-sign.sh signs an image on a local registry exactly as CI does;
#   image/signing.sh writes the policy exactly as the image build does;
#   skopeo (same containers/image library bootc uses) must then
#     accept the signed image, and reject an unsigned one and a wrong-key one,
#     while images from other repos are still accepted unsigned;
#   and the policy's top-level default must be "reject": bootc refuses to
#     enforce signatures under an insecureAcceptAnything default (found on the
#     laptop: "containers-policy.json specifies a default of
#     insecureAcceptAnything; refusing usage").
# Needs: podman, skopeo, cosign, jq, openssl. Run from the repo root (CI does).
# =============================================================================
set -euo pipefail

work=$(mktemp -d)
cleanup() { podman rm -f tos-test-registry >/dev/null 2>&1 || true; rm -rf "$work"; }
trap cleanup EXIT
fail() { echo "FAIL: $*"; exit 1; }

repo=localhost:5000/tegendo-test/os

# A fake repo root holding a throwaway key pair, so the real scripts run unchanged.
mkdir -p "$work/ctx/image/signing" "$work/sysroot/usr/share/containers"
openssl genpkey -algorithm EC -pkeyopt ec_paramgen_curve:P-256 -out "$work/key.pem" 2>/dev/null
openssl pkey -in "$work/key.pem" -pubout -out "$work/ctx/image/signing/cosign.pub"
openssl genpkey -algorithm EC -pkeyopt ec_paramgen_curve:P-256 -out "$work/other.pem" 2>/dev/null
# Fedora's default policy (accept anything unless a rule says otherwise).
echo '{"default":[{"type":"insecureAcceptAnything"}],"transports":{"docker":{}}}' \
  >"$work/sysroot/usr/share/containers/policy.json"

# Local registry and two tiny images.
podman run -d --rm --name tos-test-registry -p 5000:5000 docker.io/library/registry:2 >/dev/null
for _ in $(seq 1 30); do curl -sf http://localhost:5000/v2/ >/dev/null && break; sleep 1; done
push() {   # push <tag> <content>; prints the digest
  local d="$work/img-$1"
  mkdir -p "$d"
  echo "$2" >"$d/content"
  printf 'FROM scratch\nCOPY content /content\n' >"$d/Containerfile"
  podman build -q -t "$repo:$1" "$d" >/dev/null
  podman push -q --tls-verify=false --digestfile "$d/digest" "$repo:$1"
  cat "$d/digest"
}
signed=$(push signed "signed $RANDOM")
unsigned=$(push unsigned "unsigned $RANDOM")
other=$(repo=localhost:5000/someone-else/app push other "other repo $RANDOM")
wrongkey=$(push wrongkey "wrong key $RANDOM")

COSIGN_PRIVATE_KEY=$(cat "$work/key.pem") tools/ci-sign.sh "$repo@$signed" \
  --allow-insecure-registry --tlog-upload=false >/dev/null
COSIGN_PRIVATE_KEY=$(cat "$work/other.pem") tools/ci-sign.sh "$repo@$wrongkey" \
  --allow-insecure-registry --tlog-upload=false >/dev/null

# Policy exactly as the image gets it, then point keyPath into the scratch root.
image/signing.sh "$work/ctx" "$repo" "$work/sysroot" >/dev/null
jq --arg repo "$repo" --arg key "$work/sysroot/etc/pki/containers/tegendo-os.pub" \
  '.transports.docker[$repo][0].keyPath = $key' \
  "$work/sysroot/etc/containers/policy.json" >"$work/policy.json"

fetch() {   # fetch <digest> [repo]: copy with the policy enforced
  skopeo --registries.d "$work/sysroot/etc/containers/registries.d" copy -q \
    --policy "$work/policy.json" --src-tls-verify=false \
    "docker://${2:-$repo}@$1" "dir:$work/out-$RANDOM"
}

fetch "$signed" || fail "the correctly signed image was rejected"
echo "ok: signed image accepted"
if fetch "$unsigned" 2>"$work/err"; then fail "an unsigned image was accepted"; fi
echo "ok: unsigned image rejected ($(head -c 120 "$work/err"))"
if fetch "$wrongkey" 2>"$work/err"; then fail "an image signed with another key was accepted"; fi
echo "ok: wrong-key image rejected ($(head -c 120 "$work/err"))"
fetch "$other" localhost:5000/someone-else/app || fail "an image from another repo was rejected"
echo "ok: other repos unaffected"
jq -e '.default == [{"type": "reject"}]' "$work/policy.json" >/dev/null ||
  fail "top-level default must be reject, or bootc refuses to enforce"
for t in docker docker-daemon docker-archive oci oci-archive containers-storage dir tarball; do
  jq -e --arg t "$t" '.transports[$t][""] == [{"type": "insecureAcceptAnything"}]' "$work/policy.json" >/dev/null ||
    fail "transport $t lost its allow-everything default"
done
echo "ok: default reject, every transport still allows other images"
echo "signing policy: all checks passed"

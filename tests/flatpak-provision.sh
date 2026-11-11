#!/usr/bin/env bash
# Tests tos-flatpak-provision against a stub flatpak: the real image list
# parses, runtime-of picks the app's runtime branch, present apps are skipped,
# failures leave no stamp, and an unchanged list is a no-op.
set -euo pipefail

root=$(cd "$(dirname "$0")/.." && pwd)
tmp=$(mktemp -d)
trap 'rm -rf "$tmp"' EXIT

# Stub: Steam installed on runtime branch 25.08, Flatseal installed, nothing
# else; installs succeed unless FAIL_INSTALL is set. Every call is logged.
cat >"$tmp/flatpak" <<'EOF'
#!/usr/bin/env bash
echo "$*" >>"$STUB_LOG"
case "$1 $2" in
  "info --system")
    if [[ $3 == --show-runtime ]]; then
      [[ $4 == com.valvesoftware.Steam ]] && { echo "org.freedesktop.Platform/x86_64/25.08"; exit 0; }
      exit 1
    fi
    [[ $3 == com.valvesoftware.Steam || $3 == com.github.tchx84.Flatseal ]] && exit 0
    exit 1 ;;
  "install --system") [[ -n ${FAIL_INSTALL:-} ]] && exit 1; exit 0 ;;
esac
exit 0
EOF
chmod +x "$tmp/flatpak"

export TOS_FLATPAK_BIN="$tmp/flatpak" TOS_FLATPAK_LIST="$root/image/flatpaks.txt" TOS_STATE_DIR="$tmp/state" STUB_LOG="$tmp/log"
prov="$root/src/libexec/tos-flatpak-provision"
fail() { echo "FAIL: $*"; echo "--- stub log"; cat "$STUB_LOG"; exit 1; }

# 1. failure: no stamp, non-zero exit
: >"$STUB_LOG"
FAIL_INSTALL=1 "$prov" >/dev/null 2>&1 && fail "should exit non-zero when an install fails"
[[ ! -e $tmp/state/flatpaks.sha256 ]] || fail "stamp written after a failure"

# 2. success
: >"$STUB_LOG"
"$prov" >"$tmp/out"
grep -qx 'remote-modify --system --enable --no-filter flathub' "$STUB_LOG" || fail "flathub not unfiltered"
grep -qx 'install --system --noninteractive -y flathub org.freedesktop.Platform.VulkanLayer.MangoHud//25.08' "$STUB_LOG" || fail "MangoHud not on Steam's runtime branch"
grep -qx 'install --system --noninteractive -y flathub org.freedesktop.Platform.VulkanLayer.gamescope//25.08' "$STUB_LOG" || fail "gamescope not on Steam's runtime branch"
grep -qx 'install --system --noninteractive -y flathub net.davidotek.pupgui2' "$STUB_LOG" || fail "ProtonUp-Qt not installed"
grep -q 'install .*com.valvesoftware.Steam$' "$STUB_LOG" && fail "re-installed Steam, which was present"
grep -q 'install .*Flatseal' "$STUB_LOG" && fail "re-installed Flatseal, which was present"
grep -q 'heroic' "$STUB_LOG" && fail "installed a commented-out app"
[[ -s $tmp/state/flatpaks.sha256 ]] || fail "no stamp after success"

# 3. unchanged list: no flatpak calls at all
: >"$STUB_LOG"
"$prov" | grep -q unchanged || fail "unchanged list should be a no-op"
[[ ! -s $STUB_LOG ]] || fail "flatpak was called for an unchanged list"

# 4. invalid lines are rejected, not passed to flatpak
# shellcheck disable=SC2016  # literal $(id) on purpose
printf 'com.valvesoftware.Steam\n--user evil\nfoo.bar.baz runtime-of=$(id)\n' >"$tmp/bad.txt"
: >"$STUB_LOG"
TOS_FLATPAK_LIST="$tmp/bad.txt" TOS_STATE_DIR="$tmp/state2" "$prov" >/dev/null 2>&1 && fail "invalid lines should fail the run"
# shellcheck disable=SC2016
grep -q -- '--user evil\|\$(id)' "$STUB_LOG" && fail "invalid input reached flatpak"

echo "tos-flatpak-provision: all checks passed"

#!/usr/bin/env bash
# =============================================================================
# upstream-sync.sh — pull ONLY allowlisted data from Omarchy, pinned by commit.
#
# Omarchy never updates this machine on its own. This script is the single
# door upstream content comes through, and it only stages changes: you review
# them with `git diff` and commit them yourself.
#
#   tools/upstream-sync.sh status          # pinned commit vs newest upstream tags
#   tools/upstream-sync.sh diff <ref>      # what <ref> would change, allowlist only
#   tools/upstream-sync.sh apply <ref>     # stage <ref> into vendor/omarchy/
#
# <ref> is a tag (v4.5.0), a branch, or a commit. The lock records the full
# commit SHA, so what you reviewed is exactly what stays pinned.
# =============================================================================
set -euo pipefail

ROOT=$(cd "$(dirname "$0")/.." && pwd)
VENDOR="$ROOT/vendor/omarchy"
LOCK="$VENDOR/UPSTREAM.lock"
REPO_URL="https://github.com/basecamp/omarchy.git"
CACHE="${XDG_CACHE_HOME:-$HOME/.cache}/tegendo-os/omarchy.git"

# source path in Omarchy  ->  destination under vendor/omarchy/
ALLOW=(
  "themes/                                  themes/"
  "default/themed/                          themed/"
  "default/agents/skills/diagnose-crash/SKILL.md  skills/diagnose-crash/SKILL.md"
  "LICENSE                                  LICENSE"
)

# Anything outside these extensions is refused. .lua/.json are theme payloads
# for Neovim/VS Code; they are listed in the review output so you see them.
OK_EXT='toml|tpl|png|jpg|jpeg|webp|lua|json|theme|md|rgb|conf|css|yaml|ini|txt'
REVIEW_EXT='lua|json'
MAX_BYTES=$((20 * 1024 * 1024))

die() { echo "upstream-sync: $*" >&2; exit 1; }

git -C "$ROOT" rev-parse --git-dir >/dev/null 2>&1 ||
  die "$ROOT is not a git repo — run this from your tegendo-os clone"

fetch() {
  if [[ ! -d $CACHE ]]; then
    mkdir -p "$(dirname "$CACHE")"
    git clone --quiet --bare --filter=blob:none "$REPO_URL" "$CACHE"
  fi
  git -C "$CACHE" fetch --quiet --tags --force origin '+refs/heads/*:refs/heads/*'
}

resolve() { git -C "$CACHE" rev-parse --verify --quiet "$1^{commit}" || die "unknown ref: $1"; }

pinned() { [[ -f $LOCK ]] && awk -F' = ' '$1=="commit"{print $2}' "$LOCK"; }

export_tree() {  # export <commit> <dir>
  mkdir -p "$2"
  git -C "$CACHE" archive "$1" | tar -x -C "$2"
}

copy_allowlisted() {  # copy_allowlisted <src-tree> <dst-root>
  local src=$1 dst=$2 line from to
  for line in "${ALLOW[@]}"; do
    read -r from to <<<"$line"
    [[ -e $src/$from ]] || die "allowlisted path missing upstream: $from"
    mkdir -p "$dst/$(dirname "$to")"
    if [[ -d $src/$from ]]; then
      rm -rf "${dst:?}/$to"; mkdir -p "$dst/$to"
      cp -R "$src/$from." "$dst/$to"
    else
      cp "$src/$from" "$dst/$to"
    fi
  done
}

validate() {  # validate <dir>  — refuse anything that could run
  local dir=$1 bad=0 f
  while IFS= read -r -d '' f; do
    echo "  REFUSED symlink: ${f#"$dir"/}" >&2; bad=1
  done < <(find "$dir" -type l -print0)
  while IFS= read -r -d '' f; do
    echo "  REFUSED executable bit: ${f#"$dir"/}" >&2; bad=1
  done < <(find "$dir" -type f -perm /111 -print0)
  while IFS= read -r -d '' f; do
    [[ ${f##*/} == LICENSE ]] && continue
    [[ ${f,,} =~ \.($OK_EXT)$ ]] || { echo "  REFUSED file type: ${f#"$dir"/}" >&2; bad=1; }
    (( $(stat -c %s "$f") <= MAX_BYTES )) || { echo "  REFUSED >20MB: ${f#"$dir"/}" >&2; bad=1; }
  done < <(find "$dir" -type f -print0)
  (( bad == 0 )) || die "validation failed — nothing was changed"
}

review_list() {  # list code-adjacent payloads that changed, for eyes-on review
  git -C "$ROOT" status --porcelain -- vendor/omarchy | awk '{print $2}' |
    grep -E "\.($REVIEW_EXT)$" || true
}

cmd_status() {
  fetch
  local pin; pin=$(pinned || true)
  echo "pinned : ${pin:-<none>} $(awk -F' = ' '$1=="ref"{print "("$2")"}' "$LOCK" 2>/dev/null)"
  echo "latest tags:"
  git -C "$CACHE" tag --sort=-creatordate | head -5 | sed 's/^/  /'
  echo "master : $(git -C "$CACHE" rev-parse --short master 2>/dev/null || echo '?')"
}

cmd_diff() {
  local ref=${1:?usage: diff <ref>} pin commit tmp
  fetch
  commit=$(resolve "$ref"); pin=$(pinned || true)
  [[ -n $pin ]] || die "nothing pinned yet; run: apply $ref"
  local paths=(); for line in "${ALLOW[@]}"; do read -r from _ <<<"$line"; paths+=("$from"); done
  git -C "$CACHE" diff --stat "$pin" "$commit" -- "${paths[@]}"
  echo
  echo "Full diff: git -C $CACHE diff $pin $commit -- ${paths[*]}"
}

cmd_apply() {
  local ref=${1:?usage: apply <ref>} commit stage
  fetch
  commit=$(resolve "$ref")
  SYNC_TMP=$(mktemp -d); trap 'rm -rf "$SYNC_TMP"' EXIT
  local tmp=$SYNC_TMP
  export_tree "$commit" "$tmp/src"
  stage="$tmp/stage"; mkdir -p "$stage"
  copy_allowlisted "$tmp/src" "$stage"
  echo "Validating..."
  validate "$stage"

  # No upstream code runs here. Renderer parity (which does execute Omarchy's
  # renderer, in a throwaway HOME) is CI's job: .github/workflows/ci.yml.

  rm -rf "${VENDOR:?}"; mkdir -p "$VENDOR"
  cp -R "$stage/." "$VENDOR/"
  cat >"$LOCK" <<EOF
# Managed by tools/upstream-sync.sh — do not edit by hand.
repo = $REPO_URL
ref = $ref
commit = $commit
synced = $(date -u +%Y-%m-%dT%H:%M:%SZ)
EOF

  echo
  echo "Staged Omarchy ${ref} (${commit:0:12}) into vendor/omarchy/. Nothing is committed."
  git -C "$ROOT" status --short -- vendor/omarchy | head -40
  local review; review=$(review_list)
  if [[ -n $review ]]; then
    echo
    echo "Review these by eye (Neovim/VS Code payloads):"
    while IFS= read -r line; do echo "  $line"; done <<<"$review"
  fi
  echo
  echo "Next: git diff -- vendor/omarchy, then commit on a branch and open a PR."
  echo "      CI runs the renderer parity check; merge only when it's green."
}

case "${1:-}" in
  status) cmd_status ;;
  diff)   shift; cmd_diff "$@" ;;
  apply)  shift; cmd_apply "$@" ;;
  *) sed -n '2,15p' "$0"; exit 1 ;;
esac

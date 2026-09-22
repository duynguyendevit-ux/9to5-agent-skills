#!/usr/bin/env bash
# Install the skills in this repository into the agent skill directories.
#
#   ./install.sh            symlink each skill (default; edits propagate immediately)
#   ./install.sh --copy     copy instead of symlink
#   ./install.sh --dry-run  print the actions without changing anything
#
# Existing entries that are not symlinks into this repository are moved to
# <target>.bak.<timestamp> before being replaced, never deleted.

set -euo pipefail

MODE="link"
DRY_RUN=0
for arg in "$@"; do
  case "$arg" in
    --copy) MODE="copy" ;;
    --dry-run) DRY_RUN=1 ;;
    -h|--help) sed -n '2,10p' "$0"; exit 0 ;;
    *) echo "unknown option: $arg" >&2; exit 2 ;;
  esac
done

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SRC="$REPO/skills"

TARGETS=(
  "$HOME/.config/opencode/skills"
  "$HOME/.agents/skills"
  "$HOME/.claude/skills"
  "$HOME/.codex/skills"
)

run() {
  if [[ "$DRY_RUN" -eq 1 ]]; then
    printf '  [dry-run] %s\n' "$*"
  else
    "$@"
  fi
}

for target in "${TARGETS[@]}"; do
  echo "$target"
  run mkdir -p "$target"
  for src in "$SRC"/*/; do
    name="$(basename "$src")"
    dest="$target/$name"

    if [[ -L "$dest" ]] && [[ "$(readlink -f "$dest")" == "$(readlink -f "$src")" ]]; then
      echo "  = $name (already installed)"
      continue
    fi

    if [[ -e "$dest" || -L "$dest" ]]; then
      backup="$dest.bak.$(date +%s)"
      echo "  ! $name exists -> $backup"
      run mv "$dest" "$backup"
    fi

    if [[ "$MODE" == "copy" ]]; then
      echo "  + $name (copy)"
      run cp -r "$src" "$dest"
    else
      echo "  + $name (link)"
      run ln -s "${src%/}" "$dest"
    fi
  done
done

echo
if [[ "$DRY_RUN" -eq 1 ]]; then
  echo "dry run complete; no changes made"
else
  echo "done; restart OpenCode to pick up changes"
fi

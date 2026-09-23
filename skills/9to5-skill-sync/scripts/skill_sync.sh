#!/usr/bin/env bash
# Keep the canonical skill copy, the three mirror directories, and the repository
# copy in step. Reports drift; --apply fixes it.
#
#   ./skill_sync.sh --check                 report drift, exit 1 if any
#   ./skill_sync.sh --apply                 mirror and regenerate the repo copy
#   ./skill_sync.sh --check --skill 9to5-kafka
#   ./skill_sync.sh --apply --no-repo       only refresh the mirror directories
#
# The repository copy is generated, never edited: it excludes cache.json,
# endpoints.json (local-only internal endpoints) and debug artifacts.
# Symlinked entries in the canonical directory are skipped: they point at
# working trees and package installs this script does not own.
# This script never commits and never pushes.

set -euo pipefail

SKILL_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CONFIG="$SKILL_DIR/config/paths.json"

[[ -f "$CONFIG" ]] || { echo "missing $CONFIG" >&2; exit 1; }

cfg() { python3 -c "import json,sys;d=json.load(open('$CONFIG'));v=d$1;print('\n'.join(v) if isinstance(v,list) else v)"; }
expand() { python3 -c "import os,sys;print(os.path.expanduser('$1'))"; }

CANONICAL="$(expand "$(cfg "['canonical']")")"
REPO="$(expand "$(cfg "['repo']")")"
REPO_SUB="$(cfg "['repo_skills_subdir']")"
mapfile -t MIRRORS < <(cfg "['mirrors']" | while read -r p; do expand "$p"; done)
mapfile -t EXCL_ALWAYS < <(cfg "['exclude_always']")
mapfile -t EXCL_REPO < <(cfg "['exclude_from_repo']")

MODE="check"
ONLY=""
DO_REPO=1
LEAK_CHECK=0
for arg in "$@"; do
  case "$arg" in
    --check) MODE="check" ;;
    --apply) MODE="apply" ;;
    --no-repo) DO_REPO=0 ;;
    --leak-check) LEAK_CHECK=1 ;;
    --skill) shift_next="skill" ;;
    --skill=*) ONLY="${arg#*=}" ;;
    -h|--help) sed -n '2,14p' "$0"; exit 0 ;;
    *) [[ "${shift_next:-}" == "skill" ]] && { ONLY="$arg"; shift_next=""; } || { echo "unknown option: $arg" >&2; exit 2; } ;;
  esac
done

if [[ "${shift_next:-}" == "skill" ]]; then
  echo "--skill requires a name, for example: --skill 9to5-kafka" >&2
  exit 2
fi

[[ -d "$CANONICAL" ]] || { echo "canonical skills dir not found: $CANONICAL" >&2; exit 1; }

# Hash a skill directory by relative path + content, so the same content in two
# locations produces the same digest.
skill_hash() {
  local dir="$1"; shift
  local excl=("$@")
  [[ -d "$dir" ]] || { echo "missing"; return; }
  ( cd "$dir" && find . -type f "${excl[@]}" -print0 2>/dev/null \
      | sort -z | xargs -0 -r md5sum 2>/dev/null | md5sum | cut -c1-8 )
}

find_excl_always=()
for p in "${EXCL_ALWAYS[@]}"; do
  case "$p" in
    "*.pyc") find_excl_always+=( -not -name '*.pyc' ) ;;
    *)       find_excl_always+=( -not -path "*${p}*" ) ;;
  esac
done

find_excl_repo=("${find_excl_always[@]}")
for p in "${EXCL_REPO[@]}"; do
  find_excl_repo+=( -not -path "*/${p}" )
done

skills=()
skipped=()
for d in "$CANONICAL"/*/; do
  name="$(basename "$d")"
  [[ -n "$ONLY" && "$name" != "$ONLY" ]] && continue
  # A symlink points outside the collection: it is somebody else's working tree
  # or a package-manager install, not a skill this script owns. Never mirror it
  # and never publish it.
  if [[ -L "${d%/}" ]]; then
    skipped+=("$name")
    continue
  fi
  skills+=("$name")
done
[[ ${#skills[@]} -gt 0 ]] || { echo "no skills found in $CANONICAL" >&2; exit 1; }

rsync_excludes=()
for p in "${EXCL_ALWAYS[@]}" "${EXCL_REPO[@]}"; do rsync_excludes+=( --exclude "$p" ); done

if [[ "$MODE" == "apply" ]]; then
  for m in "${MIRRORS[@]}"; do
    mkdir -p "$m"
    for name in "${skills[@]}"; do
      rsync -a --delete "${rsync_excludes[@]}" "$CANONICAL/$name/" "$m/$name/"
    done
  done
  if [[ "$DO_REPO" -eq 1 ]]; then
    mkdir -p "$REPO/$REPO_SUB"
    for name in "${skills[@]}"; do
      rsync -a --delete "${rsync_excludes[@]}" "$CANONICAL/$name/" "$REPO/$REPO_SUB/$name/"
      # Recreate only the empty-dir keepers the canonical skill actually has, so a
      # skill without a debug/ tree does not gain one in the repository.
      while IFS= read -r keep; do
        [[ -z "$keep" ]] && continue
        if [[ -e "$CANONICAL/$name/$keep" ]]; then
          mkdir -p "$(dirname "$REPO/$REPO_SUB/$name/$keep")"
          touch "$REPO/$REPO_SUB/$name/$keep"
        fi
      done < <(cfg "['keep_empty_dirs']")
    done
    find "$REPO/$REPO_SUB" -type d -empty -not -path "*/debug/artifacts" -delete 2>/dev/null || true
  fi
fi

drift=0
printf '%-34s %-10s' "skill" "canonical"
for m in "${MIRRORS[@]}"; do printf '%-10s' "$(basename "$(dirname "$m")")"; done
printf '%-10s\n' "repo"
printf '%s\n' "$(printf '%.0s-' {1..92})"

for name in "${skills[@]}"; do
  ch="$(skill_hash "$CANONICAL/$name" "${find_excl_always[@]}")"
  # The repo copy intentionally lacks cache.json / endpoints.json / debug artifacts,
  # so compare it against canonical with the same exclusions applied.
  ch_repo="$(skill_hash "$CANONICAL/$name" "${find_excl_repo[@]}")"
  printf '%-34s %-10s' "$name" "$ch"
  for m in "${MIRRORS[@]}"; do
    mh="$(skill_hash "$m/$name" "${find_excl_always[@]}")"
    printf '%-10s' "$mh"
    [[ "$mh" != "$ch" ]] && drift=$((drift + 1))
  done
  if [[ "$DO_REPO" -eq 1 ]]; then
    rh="$(skill_hash "$REPO/$REPO_SUB/$name" "${find_excl_repo[@]}")"
    if [[ "$rh" == "$ch_repo" ]]; then
      printf '%-10s' "OK"
    else
      printf '%-10s' "$rh"
      drift=$((drift + 1))
    fi
  fi
  printf '\n'
done

echo
if [[ ${#skipped[@]} -gt 0 ]]; then
  echo "skipped (symlink, not owned by this script): ${skipped[*]}"
fi
if [[ "$MODE" == "check" ]]; then
  if [[ "$drift" -gt 0 ]]; then
    echo "$drift location(s) differ from canonical — run with --apply"
  else
    echo "all locations match canonical"
  fi
else
  echo "mirrors refreshed from $CANONICAL"
  if [[ "$DO_REPO" -eq 1 ]]; then
    echo "repo copy regenerated at $REPO/$REPO_SUB (commit it yourself)"
  fi
fi

# Leak scan: derive the forbidden hostnames from the local (gitignored) endpoints
# files rather than listing them here, so the repository never contains them.
if [[ "$LEAK_CHECK" -eq 1 ]]; then
  mapfile -t LEAK_PATTERNS < <(python3 - "$CANONICAL" <<'PY'
import json, sys, urllib.parse
from pathlib import Path
canonical = Path(sys.argv[1])
hosts = set()
for f in canonical.glob("*/config/endpoints.json"):
    try:
        data = json.loads(f.read_text(encoding="utf-8"))
    except Exception:
        continue
    for value in data.values():
        if not isinstance(value, str):
            continue
        raw = value if "://" in value else "//" + value
        host = urllib.parse.urlparse(raw).hostname
        if host and host not in {"localhost", "127.0.0.1"}:
            hosts.add(host)
for h in sorted(hosts):
    print(h)
PY
)
  if [[ ${#LEAK_PATTERNS[@]} -eq 0 ]]; then
    echo "leak check: no local endpoints files to derive patterns from (nothing to compare)"
  else
    echo "leak check: ${#LEAK_PATTERNS[@]} internal host(s) derived from local config"
    leaks=0
    for host in "${LEAK_PATTERNS[@]}"; do
      n=$(grep -rl --include="*" --exclude-dir=.git "$host" "$REPO" 2>/dev/null | wc -l) || true
      if [[ "$n" -gt 0 ]]; then
        echo "  LEAK  $host appears in $n file(s):"
        grep -rl --include="*" --exclude-dir=.git "$host" "$REPO" 2>/dev/null \
          | sed "s|$REPO/|    |" | head -5 || true
        leaks=$((leaks + n))
      fi
    done
    if [[ "$leaks" -eq 0 ]]; then
      echo "  repo is free of internal hostnames"
    else
      drift=$((drift + leaks))
    fi
  fi
fi

[[ "$MODE" == "check" && "$drift" -gt 0 ]] && exit 1
exit 0

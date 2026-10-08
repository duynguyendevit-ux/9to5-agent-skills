#!/usr/bin/env bash
# hprof-autopilot — analyze JVM heap dumps headlessly with Eclipse MAT and archive reports.
#
#   hprof-autopilot scan            list dumps in DUMP_DIRS with size and age
#   hprof-autopilot analyze FILE    run MAT (leak suspects, overview, top components)
#   hprof-autopilot watch           analyze every dump without a report, then purge
#   hprof-autopilot purge           delete dumps that have a report and are older than
#                                   PURGE_RETENTION_DAYS (raw dumps only, never reports)
#   hprof-autopilot install-mat     download Eclipse MAT headless into MAT_PARENT
#
# Config: ~/.config/hprof-autopilot.conf (sourced if present); see defaults below.
# Reports land in REPORT_DIR as <dump name>_<report>.zip, unzipped next to the zip.
set -uo pipefail

MAT_PARENT=${MAT_PARENT:-$HOME/.local/share/eclipse-mat}
MAT_HOME=${MAT_HOME:-$MAT_PARENT/mat}
MAT_VERSION=${MAT_VERSION:-1.17.0.20260601}
JAVA_HOME=${JAVA_HOME:-$HOME/.jdks/corretto-21.0.12.1}
REPORT_DIR=${REPORT_DIR:-$HOME/workspace/heap-reports}
DUMP_DIRS=${DUMP_DIRS:-$HOME}
PURGE_RETENTION_DAYS=${PURGE_RETENTION_DAYS:-7}
MAT_XMX=${MAT_XMX:-4g}
MAT_MAX_PER_RUN=${MAT_MAX_PER_RUN:-1}

CONF=${HPROF_AUTOPILOT_CONF:-$HOME/.config/hprof-autopilot.conf}
if [[ -f "$CONF" ]]; then
  # shellcheck disable=SC1090
  source "$CONF"
fi

export PATH="$JAVA_HOME/bin:$PATH"

usage() {
  sed -n '2,12p' "$0" | sed 's/^# \{0,1\}//'
  exit 2
}

find_dumps() {
  local dir
  for dir in $DUMP_DIRS; do
    find "$dir" -maxdepth 1 -type f -name '*.hprof' 2>/dev/null
  done | sort -u
}

report_for() {
  # MAT names reports after the dump with the .hprof suffix stripped.
  echo "$REPORT_DIR/$(basename "${1%.hprof}")_Leak_Suspects.zip"
}

cmd_scan() {
  local dump size age
  while read -r dump; do
    [[ -n "$dump" ]] || continue
    size=$(du -h "$dump" | cut -f1)
    age=$(( ( $(date +%s) - $(date -r "$dump" +%s) ) / 86400 ))
    printf '%8s | %4sd old | %s\n' "$size" "$age" "$dump"
  done < <(find_dumps)
}

cmd_install_mat() {
  local url tmp
  url="https://download.eclipse.org/mat/1.17.0/rcp/MemoryAnalyzer-${MAT_VERSION}-linux.gtk.x86_64.zip"
  tmp=$(mktemp -d /tmp/opencode/mat.XXXXXX)
  echo "downloading $url"
  if ! curl -sSL -o "$tmp/mat.zip" "$url"; then
    echo "download failed" >&2
    return 1
  fi
  mkdir -p "$MAT_PARENT"
  unzip -q -o "$tmp/mat.zip" -d "$MAT_PARENT"
  if [[ -x "$MAT_HOME/ParseHeapDump.sh" ]]; then
    echo "MAT installed: $MAT_HOME"
  else
    echo "unexpected layout — ParseHeapDump.sh not found under $MAT_HOME" >&2
    return 1
  fi
}

cmd_analyze() {
  local dump="$1" staging rc zip
  if [[ ! -f "$dump" ]]; then
    echo "no such dump: $dump" >&2
    return 1
  fi
  if [[ ! -x "$MAT_HOME/MemoryAnalyzer" ]]; then
    echo "MAT not found at $MAT_HOME — run: hprof-autopilot install-mat" >&2
    return 1
  fi
  mkdir -p "$REPORT_DIR"
  staging=$(mktemp -d /tmp/opencode/hprof.XXXXXX)
  echo "analyzing $(du -h "$dump" | cut -f1) $dump (MAT heap ${MAT_XMX})"
  # Invoke MemoryAnalyzer directly: ParseHeapDump.sh shares one default workspace and
  # failed with rc=14 once a previous run held it; a staging -data dir per run avoids locks.
  nice -n 19 "$MAT_HOME/MemoryAnalyzer" \
    -consolelog -nosplash \
    -vm "$JAVA_HOME/bin/java" \
    -data "$staging/workspace" \
    -application org.eclipse.mat.api.parse \
    "$dump" \
    org.eclipse.mat.api:suspects \
    org.eclipse.mat.api:overview \
    org.eclipse.mat.api:top_components \
    -vmargs "-Xmx${MAT_XMX}" 2>&1 | tee "$staging/mat.log"
  rc=${PIPESTATUS[0]}
  if [[ $rc -ne 0 ]]; then
    echo "MAT failed with rc=$rc — full log: $staging/mat.log" >&2
    return $rc
  fi
  shopt -s nullglob
  local stem="${dump%.hprof}"
  for zip in "$stem"_*.zip; do
    mv "$zip" "$REPORT_DIR/"
    unzip -q -o "$REPORT_DIR/$(basename "$zip")" -d "$REPORT_DIR/$(basename "$zip" .zip)" \
      || echo "warning: could not unzip $zip" >&2
  done
  shopt -u nullglob
  rm -rf "${stem}.index" "${stem}".*.index "${stem}.threads" 2>/dev/null
  echo "report(s) archived under $REPORT_DIR"
}

cmd_purge() {
  local dump report age
  while read -r dump; do
    [[ -n "$dump" ]] || continue
    report=$(report_for "$dump")
    if [[ ! -f "$report" ]]; then
      echo "keep (no report yet): $dump"
      continue
    fi
    age=$(( ( $(date +%s) - $(date -r "$dump" +%s) ) / 86400 ))
    if (( age >= PURGE_RETENTION_DAYS )); then
      rm -f "$dump"
      echo "purged (report present, ${age}d old): $dump"
    else
      echo "keep (${age}d < ${PURGE_RETENTION_DAYS}d retention): $dump"
    fi
  done < <(find_dumps)
}

cmd_watch() {
  local dump rc=0 done_count=0
  while read -r dump; do
    [[ -n "$dump" ]] || continue
    [[ -f "$(report_for "$dump")" ]] && continue
    if (( done_count >= MAT_MAX_PER_RUN )); then
      echo "deferring analysis of remaining dumps to the next run (MAT_MAX_PER_RUN=$MAT_MAX_PER_RUN)"
      break
    fi
    cmd_analyze "$dump" || rc=1
    done_count=$((done_count + 1))
  done < <(find_dumps)
  cmd_purge
  return $rc
}

case "${1:-}" in
  scan) cmd_scan ;;
  analyze) [[ $# -ge 2 ]] || usage; cmd_analyze "$2" ;;
  watch) cmd_watch ;;
  purge) cmd_purge ;;
  install-mat) cmd_install_mat ;;
  *) usage ;;
esac

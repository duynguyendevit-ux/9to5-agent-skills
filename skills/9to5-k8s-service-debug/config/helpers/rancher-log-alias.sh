#!/usr/bin/env bash

# Source this file from ~/.bashrc or ~/.bash_aliases:
#   source /home/example/workspace/k8slog/rancher-log-alias.sh

# Rancher kubeconfig file.
export KUBECONFIG="/home/example/Downloads/example-dev-context.yaml"
KUBECTL_BIN="/usr/bin/kubectl"
KUBE_SELECTED_NAMESPACE=""
KUBE_SELECTED_POD=""

_require_kubectl() {
  if [[ ! -x "$KUBECTL_BIN" ]]; then
    echo "kubectl not found at $KUBECTL_BIN." >&2
    return 1
  fi
}

_kube_pick_pod() {
  local app="$1"
  local namespace="$2"
  local context="$3"

  local kube_args=()
  if [[ -n "$context" ]]; then
    kube_args+=(--context "$context")
  fi

  local matches=()
  local choice=""
  local i
  local scope_args=()

  KUBE_SELECTED_NAMESPACE=""
  KUBE_SELECTED_POD=""

  if [[ -n "$namespace" ]]; then
    scope_args=(-n "$namespace")
    mapfile -t matches < <(
      "$KUBECTL_BIN" "${kube_args[@]}" get pods "${scope_args[@]}" --no-headers 2>/dev/null \
        | awk -v ns="$namespace" '{print ns "|" $1}' \
        | awk -F'|' -v app="$app" 'index($2, app) > 0' || true
    )
  else
    scope_args=(-A)
    mapfile -t matches < <(
      "$KUBECTL_BIN" "${kube_args[@]}" get pods "${scope_args[@]}" --no-headers 2>/dev/null \
        | awk '{print $1 "|" $2}' \
        | awk -F'|' -v app="$app" 'index($2, app) > 0' || true
    )
  fi

  if [[ "${#matches[@]}" -eq 0 ]]; then
    return 1
  fi

  if [[ "${#matches[@]}" -eq 1 ]]; then
    KUBE_SELECTED_NAMESPACE="${matches[0]%%|*}"
    KUBE_SELECTED_POD="${matches[0]#*|}"
    return 0
  fi

  if [[ -n "$namespace" ]]; then
    echo "Multiple pods found for '$app' in namespace '$namespace':" >&2
  else
    echo "Multiple pods found for '$app' across namespaces:" >&2
  fi
  for i in "${!matches[@]}"; do
    printf '%d) %s\n' "$((i + 1))" "${matches[$i]}" >&2
  done

  if [[ ! -t 0 ]]; then
    echo "Run this command in an interactive shell to select a pod, or pass the namespace explicitly." >&2
    return 1
  fi

  while true; do
    read -r -p "Select pod number: " choice
    if [[ "$choice" =~ ^[0-9]+$ ]] && (( choice >= 1 && choice <= ${#matches[@]} )); then
      KUBE_SELECTED_NAMESPACE="${matches[$((choice - 1))]%%|*}"
      KUBE_SELECTED_POD="${matches[$((choice - 1))]#*|}"
      return 0
    fi
    echo "Invalid selection. Enter a number between 1 and ${#matches[@]}." >&2
  done
}

klog() {
  local app="${1:-}"
  local namespace="${2:-}"
  local context="${3:-}"

  _require_kubectl || return 1

  if [[ -z "$app" ]]; then
    echo "Usage: klog <app-name> [namespace] [context]" >&2
    return 1
  fi

  local kube_args=()
  if [[ -n "$context" ]]; then
    kube_args+=(--context "$context")
  fi

  if ! _kube_pick_pod "$app" "$namespace" "$context"; then
    if [[ -n "$namespace" ]]; then
      echo "No pod found for app '$app' in namespace '$namespace'." >&2
    else
      echo "No pod found for app '$app' in any namespace." >&2
    fi
    return 1
  fi

  local pod_namespace="$KUBE_SELECTED_NAMESPACE"
  local pod="$KUBE_SELECTED_POD"

  echo "Using pod: $pod (namespace: $pod_namespace)" >&2
  "$KUBECTL_BIN" "${kube_args[@]}" -n "$pod_namespace" logs -f "$pod" --tail=500
}

klogs() {
  klog "$@"
}

kfind() {
  local app="${1:-}"
  local pattern="${2:-}"
  local namespace="${3:-}"
  local context="${4:-}"

  _require_kubectl || return 1

  if [[ -z "$app" || -z "$pattern" ]]; then
    echo "Usage: kfind <app-name> <text-pattern> [namespace] [context]" >&2
    return 1
  fi

  local kube_args=()
  if [[ -n "$context" ]]; then
    kube_args+=(--context "$context")
  fi

  if ! _kube_pick_pod "$app" "$namespace" "$context"; then
    if [[ -n "$namespace" ]]; then
      echo "No pod found for app '$app' in namespace '$namespace'." >&2
    else
      echo "No pod found for app '$app' in any namespace." >&2
    fi
    return 1
  fi

  local pod_namespace="$KUBE_SELECTED_NAMESPACE"
  local pod="$KUBE_SELECTED_POD"

  echo "Using pod: $pod (namespace: $pod_namespace)" >&2
  "$KUBECTL_BIN" "${kube_args[@]}" -n "$pod_namespace" logs -f "$pod" --tail=500 \
    | grep -i --line-buffered --color=auto "$pattern"
}

_hibernate_bind_sql_stream() {
  LC_ALL=C perl -CSDA -Mstrict -Mwarnings -e "$(cat <<'PERL'
my $sql = "";
my %values;
my %types;
my $collecting_sql = 0;
my $emitted_count = 0;
my @pending_worker_sql;

sub reset_state {
  $sql = "";
  %values = ();
  %types = ();
  $collecting_sql = 0;
}

sub trim {
  my ($value) = @_;
  $value =~ s/^\s+//;
  $value =~ s/\s+$//;
  return $value;
}

sub placeholder_count {
  my ($value) = @_;
  my @matches = ($value =~ /\?/g);
  return scalar @matches;
}

sub append_sql_part {
  my ($part) = @_;
  $part = trim($part);
  return if $part eq "";
  $sql .= " " if $sql ne "";
  $sql .= $part;
}

sub sql_literal {
  my ($value, $type) = @_;
  $type = "" unless defined $type;
  return "null" if !defined($value) || lc($value) eq "null";

  if ($type =~ /BOOLEAN/i) {
    return "1" if $value =~ /^(?:true|1)$/i;
    return "0" if $value =~ /^(?:false|0)$/i;
  }
  return $value if $type =~ /(?:INTEGER|BIGINT|SMALLINT|TINYINT|DOUBLE|FLOAT|REAL|NUMERIC|DECIMAL)/i
    && $value =~ /^-?\d+(?:\.\d+)?$/;
  if ($type =~ /TIMESTAMP/i) {
    $value =~ s/T/ /;
    $value =~ s/'/''/g;
    return "TIMESTAMP '" . $value . "'";
  }

  $value =~ s/'/''/g;
  return "'" . $value . "'";
}

sub format_sql {
  my ($value) = @_;
  $value = trim($value);
  $value =~ s/\s+/ /g;
  $value =~ s/\s*;\s*$//;
  return $value . ";";
}

sub infer_business {
  my ($value) = @_;

  return "no-contact-60s"
    if $value =~ /"no_verification_at"/ && $value =~ /"auto_calls"/;
  return "no-final-verification-milestone"
    if $value =~ /"event_elevate_level_histories"/ && $value =~ /"elevate_type"/;
  return "dispatch-level-2"
    if $value =~ /"event_level"\s*<\s*2/;
  return "dispatch-level-3"
    if $value =~ /"event_level"\s*<\s*3/;
  return "device-state-expiration"
    if $value =~ /"device_state_queues"/ && $value =~ /"expiration_at"/;

  return "unknown";
}

sub print_sql {
  my ($bound_sql, $business) = @_;

  print "\n" if $emitted_count > 0;
  print "-- Business: " . $business . "\n";
  print format_sql($bound_sql) . "\n";
  $emitted_count++;
}

sub supports_worker_metadata {
  my ($business) = @_;
  return $business =~ /^(?:dispatch-level-2|dispatch-level-3|no-contact-60s|no-final-verification-milestone)$/;
}

sub bind_worker_metadata {
  my ($value, $business, $cutoff, $limit) = @_;
  my $timestamp = sql_literal($cutoff, "TIMESTAMP");

  $value =~ s/("created_date_time"\s*<=\s*)\?/$1$timestamp/;
  if ($business eq "no-final-verification-milestone") {
    $value =~ s/("elevate_type"\s*=\s*)\?/${1}'NO_VERIFICATION_15_MINUTES'/;
  }
  $value =~ s/(\boffset\s+)\?(\s+rows\s+fetch\s+first\s+)\?(\s+rows\s+only)/${1}0${2}${limit}${3}/i;

  return $value;
}

sub emit_pending_worker_sql {
  my ($business, $cutoff, $limit) = @_;

  for my $pending (@pending_worker_sql) {
    next if $pending->{emitted};
    next if $pending->{business} ne $business;

    my $bound_sql = bind_worker_metadata($pending->{sql}, $business, $cutoff, $limit);
    print_sql($bound_sql, $business);
    $pending->{emitted} = 1;
    return;
  }
}

sub finish_sql {
  return if $sql eq "";

  my $bound_sql = $sql;
  for my $idx (sort { $a <=> $b } keys %values) {
    my $literal = sql_literal($values{$idx}, $types{$idx});
    $bound_sql =~ s/\?/$literal/;
  }

  my $business = infer_business($bound_sql);
  if (supports_worker_metadata($business) && placeholder_count($bound_sql) > 0 && !%values) {
    push @pending_worker_sql, {
      business => $business,
      sql => $bound_sql,
      emitted => 0,
    };
  } else {
    print_sql($bound_sql, $business);
  }
  reset_state();
}

sub flush_pending_worker_sql {
  for my $pending (@pending_worker_sql) {
    next if $pending->{emitted};
    print_sql($pending->{sql}, $pending->{business});
    $pending->{emitted} = 1;
  }
}

while (my $line = <STDIN>) {
  chomp $line;

  if ($line =~ /binding parameter \[(\d+)\] as \[([^\]]+)\] - \[(.*)\]/) {
    my ($idx, $type, $value) = ($1, $2, $3);
    $value =~ s/\]".*$//;
    $values{$idx} = $value;
    $types{$idx} = $type;
    $collecting_sql = 0;

    my $placeholders = placeholder_count($sql);
    finish_sql() if $placeholders > 0 && scalar(keys %values) >= $placeholders;
    next;
  }

  if ($line =~ /\[EventHandleWorkerQuery\]\s+worker=([^,"]+).*?cutoff=([^,"]+).*?limit=(\d+)/) {
    my ($business, $cutoff, $limit) = ($1, $2, $3);
    finish_sql() if $sql ne "";
    emit_pending_worker_sql($business, $cutoff, $limit);
    next;
  }

  if ($line =~ /^\s*Hibernate:\s*(.*)$/) {
    finish_sql() if $sql ne "";
    reset_state();
    $collecting_sql = 1;
    append_sql_part($1);
    next;
  }

  if ($collecting_sql && $line =~ /^\s*\{/) {
    finish_sql();
    next;
  }

  append_sql_part($line) if $collecting_sql;
}

finish_sql() if $sql ne "";
flush_pending_worker_sql();
PERL
)"
}

ksql() {
  if [[ ! -t 0 && "$#" -eq 0 ]]; then
    _hibernate_bind_sql_stream
    return
  fi

  local app="${1:-}"
  local namespace="${2:-}"
  local context="${3:-}"

  _require_kubectl || return 1

  if [[ -z "$app" ]]; then
    echo "Usage: ksql <app-name> [namespace] [context]" >&2
    echo "       klog <app-name> [namespace] [context] | ksql" >&2
    return 1
  fi

  local kube_args=()
  if [[ -n "$context" ]]; then
    kube_args+=(--context "$context")
  fi

  if ! _kube_pick_pod "$app" "$namespace" "$context"; then
    if [[ -n "$namespace" ]]; then
      echo "No pod found for app '$app' in namespace '$namespace'." >&2
    else
      echo "No pod found for app '$app' in any namespace." >&2
    fi
    return 1
  fi

  local pod_namespace="$KUBE_SELECTED_NAMESPACE"
  local pod="$KUBE_SELECTED_POD"

  echo "Using pod: $pod (namespace: $pod_namespace)" >&2
  "$KUBECTL_BIN" "${kube_args[@]}" -n "$pod_namespace" logs -f "$pod" --tail=500 \
    | _hibernate_bind_sql_stream
}

kerror() {
  local app="${1:-}"
  local namespace="${2:-}"
  local context="${3:-}"

  kfind "$app" 'error|exception|failed|fatal|panic|stacktrace' "$namespace" "$context"
}

alias kpods='/usr/bin/kubectl get pods'

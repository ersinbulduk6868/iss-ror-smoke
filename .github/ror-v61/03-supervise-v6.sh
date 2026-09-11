#!/usr/bin/env bash
set -Eeuo pipefail

mkdir -p artifacts/logs/real-ror-stall-diagnostics
HARNESS_PID=''
REAL_ROR_PID=''
STALL_CAPTURED=0

is_descendant_of_harness() {
  local pid="$1" cur="$1" ppid
  while [[ "$cur" =~ ^[0-9]+$ ]] && (( cur > 1 )); do
    [[ -r "/proc/$cur/status" ]] || return 1
    ppid="$(awk '/^PPid:/ {print $2; exit}' "/proc/$cur/status" 2>/dev/null || true)"
    [[ "$ppid" =~ ^[0-9]+$ ]] || return 1
    [[ "$ppid" == "$HARNESS_PID" ]] && return 0
    cur="$ppid"
  done
  return 1
}

find_real_ror_pid() {
  local proc pid exe
  local -a matches=()
  for proc in /proc/[0-9]*; do
    [[ -d "$proc" ]] || continue
    pid="${proc##*/}"
    exe="$(readlink -f "$proc/exe" 2>/dev/null || true)"
    [[ "$exe" == "$ROR_DIR/RoR" ]] || continue
    if is_descendant_of_harness "$pid"; then
      matches+=("$pid")
    fi
  done
  if (( ${#matches[@]} == 1 )); then
    printf '%s\n' "${matches[0]}"
    return 0
  fi
  if (( ${#matches[@]} > 1 )); then
    printf 'REAL_ROR_PID_AMBIGUOUS descendants=%s\n' "${matches[*]}" >&2
    return 2
  fi
  return 1
}

verify_real_ror_identity() {
  local pid="$1" exe
  [[ "$pid" =~ ^[0-9]+$ ]] || return 1
  kill -0 "$pid" 2>/dev/null || return 1
  exe="$(readlink -f "/proc/$pid/exe" 2>/dev/null || true)"
  [[ "$exe" == "$ROR_DIR/RoR" ]]
}

capture_real_ror_stall() {
  local label="$1" pid="$REAL_ROR_PID" out sample task tid gdb_rc
  out="artifacts/logs/real-ror-stall-diagnostics/$label"
  mkdir -p "$out/tasks"

  {
    echo "label=$label"
    echo "harness_pid=$HARNESS_PID"
    echo "real_ror_pid=$pid"
    echo "real_ror_exe=$(readlink -f /proc/$pid/exe 2>/dev/null || true)"
    echo "utc=$(date -u +%Y-%m-%dT%H:%M:%SZ)"
    echo "monotonic_ns=$(python3 - <<'PY'
import time
print(time.monotonic_ns())
PY
)"
    echo "probe_state_tail_begin=1"
    tail -n 20 artifacts/logs/probe-state-history.txt 2>/dev/null || true
    echo "probe_state_tail_end=1"
  } > "$out/context.txt"

  if ! verify_real_ror_identity "$pid"; then
    echo 'REAL_ROR_NOT_ALIVE_OR_IDENTITY_MISMATCH_AT_STALL_CAPTURE=1' >> "$out/context.txt"
    return 1
  fi
  echo 'REAL_ROR_IDENTITY_GATE=PASS' >> "$out/context.txt"

  ps -o pid,ppid,pgid,sid,psr,pcpu,pmem,stat,etime,wchan:40,comm,args -p "$pid" > "$out/ps-process.txt" 2>&1 || true
  for sample in 1 2 3; do
    ps -L -p "$pid" -o pid,tid,psr,pcpu,stat,etime,wchan:40,comm > "$out/ps-threads-${sample}.txt" 2>&1 || true
    top -H -b -n 1 -p "$pid" > "$out/top-threads-${sample}.txt" 2>&1 || true
    [[ "$sample" -lt 3 ]] && sleep 1
  done

  for f in status stat sched limits maps; do
    sudo -n cat "/proc/$pid/$f" > "$out/proc-${f}.txt" 2>&1 || true
  done
  sudo -n cat "/proc/$pid/wchan" > "$out/proc-wchan.txt" 2>&1 || true
  sudo -n cat "/proc/$pid/syscall" > "$out/proc-syscall.txt" 2>&1 || true

  for task in /proc/"$pid"/task/*; do
    [[ -d "$task" ]] || continue
    tid="${task##*/}"
    {
      echo "TID=$tid"
      sudo -n cat "$task/comm" 2>&1
      echo '--- status ---'
      sudo -n cat "$task/status" 2>&1
      echo '--- stat ---'
      sudo -n cat "$task/stat" 2>&1
      echo '--- sched ---'
      sudo -n cat "$task/sched" 2>&1
      echo '--- wchan ---'
      sudo -n cat "$task/wchan" 2>&1
      echo '--- kernel stack ---'
      sudo -n cat "$task/stack" 2>&1
    } > "$out/tasks/tid-${tid}.txt" 2>&1
  done

  for sample in 1 2 3; do
    set +e
    timeout 20s sudo -n gdb -q -batch \
      -ex 'set pagination off' \
      -ex 'set debuginfod enabled off' \
      -ex 'set print thread-events off' \
      -ex 'info threads' \
      -ex 'info sharedlibrary' \
      -ex 'info proc mappings' \
      -ex 'thread apply all bt full' \
      -p "$pid" > "$out/gdb-snapshot-${sample}.txt" 2>&1
    gdb_rc=$?
    set -e
    printf 'gdb_snapshot_%s_rc=%s\n' "$sample" "$gdb_rc" >> "$out/context.txt"
    verify_real_ror_identity "$pid" && printf 'real_ror_alive_after_gdb_%s=1\n' "$sample" >> "$out/context.txt" || printf 'real_ror_alive_after_gdb_%s=0\n' "$sample" >> "$out/context.txt"
    [[ "$sample" -lt 3 ]] && sleep 1
  done

  if [[ -n "${ROR_LOG:-}" && -f "$ROR_LOG" ]]; then
    cp "$ROR_LOG" "$out/RoR-at-real-stall.log" || true
  fi
  if [[ -n "${ROR_USER_DIR:-}" ]]; then
    find "$ROR_USER_DIR" -type f -name 'Angelscript.log' -print -quit 2>/dev/null | while IFS= read -r f; do cp "$f" "$out/Angelscript-at-real-stall.log" || true; done
  fi
  [[ -f "$RUNNER_TEMP/ror-runtime.stdout.log" ]] && cp "$RUNNER_TEMP/ror-runtime.stdout.log" "$out/ror-runtime.stdout-at-real-stall.log" || true
  echo 'REAL_ROR_STALL_DIAGNOSTICS=COMPLETE' | tee "$out/complete.txt"
}

cleanup_supervisor() {
  local rc=$?
  set +e
  if [[ -n "$REAL_ROR_PID" ]] && verify_real_ror_identity "$REAL_ROR_PID"; then
    kill -TERM "$REAL_ROR_PID" 2>/dev/null || true
    for _ in $(seq 1 20); do
      kill -0 "$REAL_ROR_PID" 2>/dev/null || break
      sleep 0.1
    done
    kill -KILL "$REAL_ROR_PID" 2>/dev/null || true
  fi
  if [[ -n "$HARNESS_PID" ]] && kill -0 "$HARNESS_PID" 2>/dev/null; then
    kill -TERM "$HARNESS_PID" 2>/dev/null || true
  fi
  printf 'SUPERVISOR_EXIT_RC=%s\n' "$rc" > artifacts/logs/real-ror-supervisor-exit.txt
  return "$rc"
}
trap cleanup_supervisor EXIT

bash .github/ror-v6/03-launch-motion.sh &
HARNESS_PID=$!
printf 'HARNESS_PID=%s\n' "$HARNESS_PID" | tee artifacts/logs/real-ror-supervisor.txt

# Discover exactly one real RoR binary while it is still a descendant of the V6 harness.
discovery_deadline=$((SECONDS + SCENE_START_TIMEOUT_SECONDS + 30))
while (( SECONDS < discovery_deadline )); do
  if candidate="$(find_real_ror_pid)"; then
    REAL_ROR_PID="$candidate"
    break
  else
    find_rc=$?
    if (( find_rc == 2 )); then
      echo 'REAL_ROR_PID_DISCOVERY_FAIL: ambiguous real RoR descendants' >&2
      exit 1
    fi
  fi
  kill -0 "$HARNESS_PID" 2>/dev/null || break
  sleep 0.1
done

if [[ -z "$REAL_ROR_PID" ]]; then
  echo 'REAL_ROR_PID_DISCOVERY_FAIL: exact RoR binary child was not discovered' >&2
  set +e
  wait "$HARNESS_PID"
  harness_rc=$?
  set -e
  exit "$harness_rc"
fi

verify_real_ror_identity "$REAL_ROR_PID" || { echo 'REAL_ROR_PID_IDENTITY_FAIL' >&2; exit 1; }
printf 'REAL_ROR_PID=%s\nREAL_ROR_EXE=%s\nREAL_ROR_PID_GATE=PASS\n' \
  "$REAL_ROR_PID" "$(readlink -f /proc/$REAL_ROR_PID/exe)" | tee -a artifacts/logs/real-ror-supervisor.txt

# Watch the unchanged V6 acceptance harness. Capture the true engine immediately when it declares a probe timeout.
while kill -0 "$HARNESS_PID" 2>/dev/null; do
  if (( STALL_CAPTURED == 0 )) && [[ -f artifacts/logs/probe-state-history.txt ]] && grep -q 'state=ACK_TIMEOUT' artifacts/logs/probe-state-history.txt; then
    label="$(awk '/state=ACK_TIMEOUT/ {for(i=1;i<=NF;i++) if($i ~ /^label=/){sub(/^label=/,"",$i); print $i; exit}}' artifacts/logs/probe-state-history.txt)"
    [[ -n "$label" ]] || label='unknown-timeout'
    capture_real_ror_stall "$label"
    STALL_CAPTURED=1
  fi
  sleep 0.05
done

set +e
wait "$HARNESS_PID"
harness_rc=$?
set -e
printf 'V6_HARNESS_RC=%s\nSTALL_CAPTURED=%s\n' "$harness_rc" "$STALL_CAPTURED" | tee -a artifacts/logs/real-ror-supervisor.txt

# If V6 timed out but the polling loop lost the race with shell exit, capture the still-live orphan before cleanup.
if (( harness_rc != 0 && STALL_CAPTURED == 0 )) && [[ -f artifacts/logs/probe-state-history.txt ]] && grep -q 'state=ACK_TIMEOUT' artifacts/logs/probe-state-history.txt; then
  label="$(awk '/state=ACK_TIMEOUT/ {for(i=1;i<=NF;i++) if($i ~ /^label=/){sub(/^label=/,"",$i); print $i; exit}}' artifacts/logs/probe-state-history.txt)"
  [[ -n "$label" ]] || label='unknown-timeout'
  if verify_real_ror_identity "$REAL_ROR_PID"; then
    capture_real_ror_stall "$label"
    STALL_CAPTURED=1
  fi
fi

if (( harness_rc != 0 )); then
  if [[ -f artifacts/logs/probe-state-history.txt ]] && grep -q 'state=ACK_TIMEOUT' artifacts/logs/probe-state-history.txt && (( STALL_CAPTURED == 0 )); then
    echo 'REAL_ROR_STALL_DIAGNOSTICS_FAIL: V6 probe timeout occurred without true-engine capture' >&2
    exit 86
  fi
  exit "$harness_rc"
fi

echo 'V6_1_SUPERVISOR_GATE=PASS' | tee artifacts/v6-1-supervisor-gate.txt

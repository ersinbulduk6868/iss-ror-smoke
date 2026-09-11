#!/usr/bin/env bash
set -euxo pipefail
mkdir -p artifacts/logs "$ROR_TEST_HOME"
XVFB_PID=''; ROR_PID=''; FFMPEG_PID=''; ANGELSCRIPT_LOG=''
cleanup() {
  set +e
  xdotool keyup Up 2>/dev/null || true
  [[ -n "$FFMPEG_PID" ]] && { kill -TERM "$FFMPEG_PID" 2>/dev/null || true; wait "$FFMPEG_PID" 2>/dev/null || true; }
  [[ -n "$ROR_PID" ]] && { kill -TERM "$ROR_PID" 2>/dev/null || true; sleep 1; kill -KILL "$ROR_PID" 2>/dev/null || true; wait "$ROR_PID" 2>/dev/null || true; }
  [[ -n "$XVFB_PID" ]] && { kill -TERM "$XVFB_PID" 2>/dev/null || true; wait "$XVFB_PID" 2>/dev/null || true; }
}
trap cleanup EXIT

Xvfb "$DISPLAY" -screen 0 1280x720x24 -ac +extension GLX +render -noreset -nolisten tcp > "$RUNNER_TEMP/xvfb.log" 2>&1 &
XVFB_PID=$!
ready=0
for _ in $(seq 1 30); do
  if xdpyinfo -display "$DISPLAY" > artifacts/logs/xdpyinfo.txt 2>&1; then ready=1; break; fi
  kill -0 "$XVFB_PID" 2>/dev/null || break
  sleep 0.5
done
(( ready == 1 )) || { cat "$RUNNER_TEMP/xvfb.log" >&2 || true; exit 1; }
glxinfo -B | tee artifacts/logs/glxinfo.txt
grep -F 'OpenGL renderer string:' artifacts/logs/glxinfo.txt
set +e; timeout 4s glxgears > artifacts/logs/glxgears.txt 2>&1; glx_rc=$?; set -e
(( glx_rc == 0 || glx_rc == 124 ))

cd "$ROR_DIR"
env -u SNAP_USER_COMMON HOME="$ROR_TEST_HOME" ./RunRoR -runscript "$PROBE_SCRIPT_NAME" -map "$ROR_MAP" -truck "$ROR_TRUCK" -enter > "$RUNNER_TEMP/ror-runtime.stdout.log" 2>&1 &
ROR_PID=$!
cd "$GITHUB_WORKSPACE"

scene_ready=0
for _ in $(seq 1 "$SCENE_START_TIMEOUT_SECONDS"); do
  sleep 1
  kill -0 "$ROR_PID" 2>/dev/null || { cat "$RUNNER_TEMP/ror-runtime.stdout.log" >&2 || true; [[ -f "$ROR_LOG" ]] && cat "$ROR_LOG" >&2 || true; exit 1; }
  if [[ -f "$ROR_LOG" ]]; then
    grep -Eqi 'Startup error|No render system plugin available|Terrain loading error|Terrain not found:|FATAL ERROR' "$ROR_LOG" && exit 1
    if awk -v map="$ROR_MAP" -v truck="$ROR_TRUCK" 'index($0,"===== LOADING TERRAIN " map){t=NR} index($0,"[RoR|Diag] Preselected Truck:")&&index($0,truck)&&t{p=NR} index($0,"===== DONE LOADING VEHICLE")&&p&&NR>p{d=NR} END{exit !(t&&p>t&&d>p)}' "$ROR_LOG"; then
      scene_ready=1
      break
    fi
  fi
done
(( scene_ready == 1 ))
sleep 2
kill -0 "$ROR_PID"

grep -F "Added resource location '$ROR_USER_SCRIPTS_DIR' of type 'FileSystem' to resource group 'Scripts'" "$ROR_LOG" || {
  echo 'SCRIPT_RESOURCE_REGISTRATION_FAIL: user scripts directory not registered by RoR' >&2
  exit 1
}
grep -F 'Parsing scripts for resource group Scripts' "$ROR_LOG" || {
  echo 'SCRIPT_RESOURCE_INITIALIZATION_FAIL: Scripts resource group not initialized' >&2
  exit 1
}
echo 'SCRIPT_RESOURCE_REGISTRATION_GATE=PASS' | tee artifacts/script-resource-registration-gate.txt

grep -F "Loading startup script '$PROBE_SCRIPT_NAME' (from command line)" "$ROR_LOG" || {
  echo 'SCRIPT_CLI_CONTRACT_FAIL: command-line startup script was not registered' >&2
  exit 1
}
! grep -F "exception upon loading script file '$PROBE_SCRIPT_NAME'" "$ROR_LOG" || {
  grep -F "exception upon loading script file '$PROBE_SCRIPT_NAME'" "$ROR_LOG" >&2 || true
  echo 'SCRIPT_RESOURCE_RESOLUTION_FAIL' >&2
  exit 1
}
! grep -F "Failed to load file '$PROBE_SCRIPT_NAME'" "$ROR_LOG" || {
  echo 'SCRIPT_RESOURCE_RESOLUTION_FAIL' >&2
  exit 1
}
echo 'SCRIPT_CLI_GATE=PASS' | tee artifacts/script-cli-gate.txt

mapfile -t angel_logs < <(find "$ROR_USER_DIR" -type f -name 'Angelscript.log' -print | sort)
test "${#angel_logs[@]}" -eq 1 || { find "$ROR_USER_DIR" -maxdepth 4 -type f -print | sort >&2 || true; echo 'SCRIPT_PROBE_LOG_DISCOVERY_FAIL' >&2; exit 1; }
ANGELSCRIPT_LOG="${angel_logs[0]}"
cp "$ANGELSCRIPT_LOG" "$GITHUB_WORKSPACE/artifacts/logs/Angelscript-initial.log"

grep -F "Executing main() in $PROBE_SCRIPT_NAME(category:CUSTOM" "$ANGELSCRIPT_LOG" || {
  cat "$ANGELSCRIPT_LOG" >&2
  echo 'SCRIPT_BUILD_MAIN_CONTRACT_FAIL: CUSTOM module main() not executed' >&2
  exit 1
}
grep -F 'ISS_MOTION_PROBE_V5_SCRIPT_MAIN' "$ANGELSCRIPT_LOG" || {
  cat "$ANGELSCRIPT_LOG" >&2
  echo 'SCRIPT_MAIN_MARKER_FAIL' >&2
  exit 1
}
! grep -Eqi 'failed to build module|exception.*occurred|script was aborted' "$ANGELSCRIPT_LOG" || {
  cat "$ANGELSCRIPT_LOG" >&2
  echo 'SCRIPT_RUNTIME_CONTRACT_FAIL' >&2
  exit 1
}
echo 'SCRIPT_BUILD_MAIN_GATE=PASS' | tee artifacts/script-build-main-gate.txt

mapfile -t runtime_input_maps < <(find "$ROR_USER_DIR" -type f -name 'input.map' -print | sort)
test "${#runtime_input_maps[@]}" -eq 1
RUNTIME_INPUT_MAP="${runtime_input_maps[0]}"
cp "$RUNTIME_INPUT_MAP" "$GITHUB_WORKSPACE/artifacts/logs/runtime-input.map"
grep -Eq '^TRUCK_ACCELERATE[[:space:]]+Keyboard[[:space:]]+UP([[:space:]]|$)' "$RUNTIME_INPUT_MAP"
grep -F 'Manager: X11InputManager' "$ROR_LOG"
grep -F 'Total Keyboards: 1' "$ROR_LOG"
grep -F ' * Loading input mapping input.map' "$ROR_LOG"
grep -F ' * Input map successfully loaded:' "$ROR_LOG"

cd "$GITHUB_WORKSPACE"
xwininfo -root -tree > artifacts/logs/xwininfo-tree.txt
ROR_WINDOW_ID="$(awk '/"Rigs of Rods version/ {print $1; exit}' artifacts/logs/xwininfo-tree.txt)"
test -n "$ROR_WINDOW_ID"
xwininfo -id "$ROR_WINDOW_ID" > artifacts/logs/xwininfo-ror.txt
xdotool windowfocus --sync "$ROR_WINDOW_ID"
sleep 1

assert_focus() {
  local focused
  focused="$(printf '0x%x' "$(xdotool getwindowfocus)")"
  printf 'expected=%s focused=%s\n' "$ROR_WINDOW_ID" "$focused" >> artifacts/logs/window-focus-history.txt
  [[ "${ROR_WINDOW_ID,,}" == "${focused,,}" ]]
}
monotonic_ns() {
  python3 - <<'PY'
import time
print(time.monotonic_ns())
PY
}
probe_count() {
  grep -F -c 'ISS_MOTION_PROBE_V5 seq=' "$ANGELSCRIPT_LOG" || true
}
wait_fresh_probe() {
  local label="$1" required_accel="${2:-any}" before now poll line sample_ns
  before="$(probe_count)"
  printf 'label=%s state=WAIT_FRESH_PROBE before=%s required_accel=%s monotonic_ns=%s\n' "$label" "$before" "$required_accel" "$(monotonic_ns)" >> artifacts/logs/probe-state-history.txt
  for poll in $(seq 1 "$PROBE_ACK_POLLS"); do
    sleep 0.1
    kill -0 "$ROR_PID" 2>/dev/null || { echo "ROR_PROCESS_DIED_DURING_PROBE label=$label poll=$poll" >&2; return 1; }
    now="$(probe_count)"
    if (( now > before )); then
      while IFS= read -r line; do
        [[ "$line" == *'ISS_MOTION_PROBE_V5 seq='* ]] || continue
        if [[ "$required_accel" != 'any' && "$line" != *" accel=$required_accel"* ]]; then
          continue
        fi
        sample_ns="$(monotonic_ns)"
        python3 - "$line" "$sample_ns" "$label" > "artifacts/logs/position-${label}.txt" <<'PY'
import re,sys
line=sys.argv[1]; ns=sys.argv[2]; label=sys.argv[3]
m=re.search(r'ISS_MOTION_PROBE_V5 seq=(\d+) x=([-+0-9.eE]+) y=([-+0-9.eE]+) z=([-+0-9.eE]+) speed=([-+0-9.eE]+) accel=([01])', line)
if not m:
    raise SystemExit(f'PROBE_PARSE_FAIL label={label}: {line!r}')
seq,x,y,z,speed,accel=m.groups()
print(f'MONOTONIC_NS={ns}')
print(f'PROBE_SEQ={seq}')
print(f'PROBE_SPEED_MPS={speed}')
print(f'PROBE_ACCEL={accel}')
print(f'Position: {x}, {y}, {z}, 0, 0, 0')
PY
        printf 'label=%s state=ACK_PASS after=%s poll=%s monotonic_ns=%s raw=%q\n' "$label" "$now" "$poll" "$sample_ns" "$line" >> artifacts/logs/probe-state-history.txt
        return 0
      done < <(grep -F 'ISS_MOTION_PROBE_V5 seq=' "$ANGELSCRIPT_LOG" | tail -n "+$((before + 1))")
    fi
  done
  echo "PROBE_ACK_FAIL: no fresh matching telemetry label=$label required_accel=$required_accel after ${PROBE_ACK_POLLS}x0.1s" >&2
  return 1
}
assert_probe_accel() {
  local file="$1" expected="$2"
  grep -Fx "PROBE_ACCEL=$expected" "$file"
}

assert_focus
wait_fresh_probe idle-start 0
sleep 2
wait_fresh_probe idle-mid 0
sleep 2
wait_fresh_probe idle-end 0
echo 'TELEMETRY_GATE=ROR_ANGELSCRIPT_ACTOR_POSITION_PASS' | tee artifacts/telemetry-gate.txt
echo 'GEAR_SELECTION=SOURCE_DEFAULT_STARTENGINE_GEAR1_DRIVE_NO_PGDOWN' | tee artifacts/gear-selection.txt

timeout "$((CAPTURE_SECONDS + 15))" ffmpeg -hide_banner -loglevel warning -y -thread_queue_size 512 \
  -f x11grab -draw_mouse 0 -video_size 1280x720 -framerate "$CAPTURE_FPS" -i "${DISPLAY}.0" \
  -t "$CAPTURE_SECONDS" -c:v libx264 -preset ultrafast -crf 23 -pix_fmt yuv420p artifacts/ror-motion-e2e.mp4 \
  > artifacts/logs/ffmpeg-capture.out 2> artifacts/logs/ffmpeg-capture.err &
FFMPEG_PID=$!
sleep 1
kill -0 "$FFMPEG_PID"

assert_focus
xdotool keyup Up 2>/dev/null || true
xdotool keydown Up
printf 'accelerator_state=KEYDOWN_HELD monotonic_ns=%s\n' "$(monotonic_ns)" | tee artifacts/logs/accelerator-state.txt
wait_fresh_probe drive-transport 1 || { xdotool keyup Up 2>/dev/null || true; echo 'ACCEL_INPUT_TRANSPORT_FAIL: RoR probe never observed accel=1' >&2; exit 1; }
assert_probe_accel artifacts/logs/position-drive-transport.txt 1
echo 'ACCEL_INPUT_TRANSPORT_GATE=ROR_APPLICATION_ACK_PASS' | tee artifacts/input-transport.txt

sleep 4
wait_fresh_probe drive-1 1
assert_probe_accel artifacts/logs/position-drive-1.txt 1
kill -0 "$ROR_PID"
sleep 4
wait_fresh_probe drive-2 1
assert_probe_accel artifacts/logs/position-drive-2.txt 1
kill -0 "$ROR_PID"
sleep 4
wait_fresh_probe drive-3 1
assert_probe_accel artifacts/logs/position-drive-3.txt 1
kill -0 "$ROR_PID"

assert_focus
xdotool keyup Up 2>/dev/null || true
printf 'accelerator_state=KEYUP_SENT monotonic_ns=%s\n' "$(monotonic_ns)" | tee -a artifacts/logs/accelerator-state.txt
wait_fresh_probe final 0 || { echo 'ACCEL_RELEASE_ACK_FAIL: RoR probe did not return accel=0' >&2; exit 1; }
assert_probe_accel artifacts/logs/position-final.txt 0
kill -0 "$ROR_PID"

wait "$FFMPEG_PID"
FFMPEG_PID=''
kill -0 "$ROR_PID"

python3 - "$MIN_HORIZONTAL_DISPLACEMENT_M" \
  artifacts/logs/position-idle-start.txt artifacts/logs/position-idle-mid.txt artifacts/logs/position-idle-end.txt \
  artifacts/logs/position-drive-1.txt artifacts/logs/position-drive-2.txt artifacts/logs/position-drive-3.txt artifacts/logs/position-final.txt \
  > artifacts/motion-evidence.txt <<'PY'
import math, re, sys
from pathlib import Path
minimum=float(sys.argv[1])
def parse(path):
    text=Path(path).read_text(errors='replace')
    m_ts=re.search(r'^MONOTONIC_NS=(\d+)\s*$', text, re.M)
    if not m_ts: raise SystemExit(f'POSITION_PARSE_FAIL {path}: missing MONOTONIC_NS')
    if 'Position:' not in text: raise SystemExit(f'POSITION_PARSE_FAIL {path}: missing Position marker')
    vals=[float(x) for x in re.findall(r'[-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][-+]?\d+)?', text.rsplit('Position:',1)[1])]
    if len(vals)<3: raise SystemExit(f'POSITION_PARSE_FAIL {path}: {text!r}')
    return tuple(vals[:3]), int(m_ts.group(1))
names=['idle_start','idle_mid','idle_end','drive_1','drive_2','drive_3','final']
parsed=dict(zip(names,map(parse,sys.argv[2:])))
pts={name: parsed[name][0] for name in names}
ts={name: parsed[name][1] for name in names}
def horizontal(a,b): return math.hypot(b[0]-a[0],b[2]-a[2])
def elapsed(a,b):
    dt=(ts[b]-ts[a])/1_000_000_000.0
    if dt <= 0.0: raise SystemExit(f'TIMING_GATE_FAIL: non-positive interval {a}->{b}: {dt}')
    return dt
idle_pairs=[('idle_start','idle_mid'),('idle_mid','idle_end')]
drive_pairs=[('idle_end','drive_1'),('drive_1','drive_2'),('drive_2','drive_3')]
idle=[horizontal(pts[a],pts[b]) for a,b in idle_pairs]
idle_dt=[elapsed(a,b) for a,b in idle_pairs]
idle_rates=[d/dt for d,dt in zip(idle,idle_dt)]
max_idle_rate=max(idle_rates)
drive=[horizontal(pts[a],pts[b]) for a,b in drive_pairs]
drive_dt=[elapsed(a,b) for a,b in drive_pairs]
drive_rates=[d/dt for d,dt in zip(drive,drive_dt)]
total=horizontal(pts['idle_end'],pts['drive_3'])
final=horizontal(pts['idle_end'],pts['final'])
for name in names:
    print(f'{name.upper()}={pts[name]}')
    print(f'{name.upper()}_MONOTONIC_NS={ts[name]}')
print('IDLE_INCREMENT_M='+','.join(f'{d:.9f}' for d in idle))
print('IDLE_INTERVAL_S='+','.join(f'{dt:.9f}' for dt in idle_dt))
print('IDLE_RATE_MPS='+','.join(f'{r:.9f}' for r in idle_rates))
print(f'MAX_IDLE_RATE_MPS={max_idle_rate:.9f}')
print('DRIVE_INCREMENT_M='+','.join(f'{d:.9f}' for d in drive))
print('DRIVE_INTERVAL_S='+','.join(f'{dt:.9f}' for dt in drive_dt))
print('DRIVE_RATE_MPS='+','.join(f'{r:.9f}' for r in drive_rates))
print(f'TOTAL_DRIVE_HORIZONTAL_DISPLACEMENT_M={total:.9f}')
print(f'FINAL_HORIZONTAL_DISPLACEMENT_M={final:.9f}')
print(f'MIN_REQUIRED_HORIZONTAL_DISPLACEMENT_M={minimum:.9f}')
if total < minimum: raise SystemExit(f'MOTION_GATE_FAIL: total {total:.9f}m < required {minimum:.9f}m')
if sum(r>max_idle_rate for r in drive_rates) < 2: raise SystemExit('MOTION_GATE_FAIL: fewer than 2/3 drive intervals exceeded measured idle rate')
if sum(d>0.0 for d in drive) < 2: raise SystemExit('MOTION_GATE_FAIL: fewer than 2/3 drive intervals changed position')
print('MOTION_GATE=PASS')
PY
cat artifacts/motion-evidence.txt
cp "$ROR_LOG" artifacts/logs/RoR-after-motion.log
cp "$ANGELSCRIPT_LOG" artifacts/logs/Angelscript-after-motion.log
cp "$RUNNER_TEMP/ror-runtime.stdout.log" artifacts/logs/ror-runtime.stdout.log
cp "$RUNNER_TEMP/xvfb.log" artifacts/logs/xvfb.log

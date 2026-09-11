#!/usr/bin/env bash
set -Eeuo pipefail
mkdir -p artifacts/logs "$ROR_TEST_HOME"
BATTLE_SCRIPT_NAME='iss_battle_probe_v81.as'
BATTLE_SCRIPT="$ROR_USER_SCRIPTS_DIR/$BATTLE_SCRIPT_NAME"
BATTLE_VIDEO='artifacts/ror-battle-e2e-v81.mp4'
XVFB_PID=''; WRAPPER_PID=''; REAL_ROR_PID=''; FFMPEG_PID=''; ANGELSCRIPT_LOG=''
cleanup() {
  local rc=$?
  set +e
  xdotool keyup Up >/dev/null 2>&1 || true
  if [[ -n "$FFMPEG_PID" ]] && kill -0 "$FFMPEG_PID" 2>/dev/null; then kill -TERM "$FFMPEG_PID" 2>/dev/null || true; wait "$FFMPEG_PID" 2>/dev/null || true; fi
  if [[ -n "$REAL_ROR_PID" ]] && kill -0 "$REAL_ROR_PID" 2>/dev/null; then kill -TERM "$REAL_ROR_PID" 2>/dev/null || true; sleep 0.5; kill -KILL "$REAL_ROR_PID" 2>/dev/null || true; fi
  if [[ -n "$WRAPPER_PID" ]] && kill -0 "$WRAPPER_PID" 2>/dev/null; then kill -TERM "$WRAPPER_PID" 2>/dev/null || true; wait "$WRAPPER_PID" 2>/dev/null || true; fi
  if [[ -n "$XVFB_PID" ]] && kill -0 "$XVFB_PID" 2>/dev/null; then kill -TERM "$XVFB_PID" 2>/dev/null || true; wait "$XVFB_PID" 2>/dev/null || true; fi
  exit "$rc"
}
trap cleanup EXIT

cp "$GITHUB_WORKSPACE/.github/ror-v81/iss_battle_probe_v81.as" "$BATTLE_SCRIPT"
cp "$BATTLE_SCRIPT" artifacts/logs/iss_battle_probe_v81.as
grep -F 'ISS_BATTLE_V81_SCRIPT_MAIN' "$BATTLE_SCRIPT"
grep -F 'ISS_BATTLE_BLOCKER_READY' "$BATTLE_SCRIPT"
grep -F 'SE_TRUCK_BEAM_BROKE' "$BATTLE_SCRIPT"
grep -F 'spawnTruckAI' "$BATTLE_SCRIPT"

Xvfb "$DISPLAY" -screen 0 1280x720x24 -ac +extension GLX +render -noreset -nolisten tcp > "$RUNNER_TEMP/xvfb-v81.log" 2>&1 &
XVFB_PID=$!
ready=0
for _ in $(seq 1 30); do
  if xdpyinfo -display "$DISPLAY" > artifacts/logs/xdpyinfo-v81.txt 2>&1; then ready=1; break; fi
  kill -0 "$XVFB_PID" 2>/dev/null || break; sleep 0.5
done
(( ready == 1 ))
glxinfo -B | tee artifacts/logs/glxinfo-v81.txt
grep -F 'OpenGL renderer string: llvmpipe' artifacts/logs/glxinfo-v81.txt

cd "$ROR_DIR"
env -u SNAP_USER_COMMON HOME="$ROR_TEST_HOME" ./RunRoR -runscript "$BATTLE_SCRIPT_NAME" -map "$ROR_MAP" -truck "$ROR_TRUCK" -enter > "$RUNNER_TEMP/ror-v81.stdout.log" 2>&1 &
WRAPPER_PID=$!
cd "$GITHUB_WORKSPACE"
printf 'WRAPPER_PID=%s\n' "$WRAPPER_PID" | tee artifacts/logs/ror-v81-pids.txt

for _ in $(seq 1 600); do
  for proc in /proc/[0-9]*; do
    [[ -d "$proc" ]] || continue
    pid="${proc##*/}"; exe="$(readlink -f "$proc/exe" 2>/dev/null || true)"
    [[ "$exe" == "$ROR_DIR/RoR" ]] || continue
    cur="$pid"
    while [[ "$cur" =~ ^[0-9]+$ ]] && (( cur > 1 )); do
      ppid="$(awk '/^PPid:/ {print $2; exit}' "/proc/$cur/status" 2>/dev/null || true)"
      [[ "$ppid" =~ ^[0-9]+$ ]] || break
      if [[ "$ppid" == "$WRAPPER_PID" ]]; then REAL_ROR_PID="$pid"; break 2; fi
      cur="$ppid"
    done
  done
  kill -0 "$WRAPPER_PID" 2>/dev/null || break; sleep 0.1
done
[[ -n "$REAL_ROR_PID" ]]
[[ "$(readlink -f "/proc/$REAL_ROR_PID/exe")" == "$ROR_DIR/RoR" ]]
printf 'REAL_ROR_PID=%s\nREAL_ROR_EXE=%s\nREAL_ROR_PID_GATE=PASS\n' "$REAL_ROR_PID" "$(readlink -f /proc/$REAL_ROR_PID/exe)" | tee -a artifacts/logs/ror-v81-pids.txt

scene_ready=0
for _ in $(seq 1 "$SCENE_START_TIMEOUT_SECONDS"); do
  sleep 1
  kill -0 "$REAL_ROR_PID" 2>/dev/null || { cat "$RUNNER_TEMP/ror-v81.stdout.log" >&2 || true; exit 1; }
  if [[ -f "$ROR_LOG" ]] && awk -v map="$ROR_MAP" -v truck="$ROR_TRUCK" 'index($0,"===== LOADING TERRAIN " map){t=NR} index($0,"[RoR|Diag] Preselected Truck:")&&index($0,truck)&&t{p=NR} index($0,"===== DONE LOADING VEHICLE")&&p&&NR>p{d=NR} END{exit !(t&&p>t&&d>p)}' "$ROR_LOG"; then scene_ready=1; break; fi
done
(( scene_ready == 1 )); sleep 1
mapfile -t angel_logs < <(find "$ROR_USER_DIR" -type f -name 'Angelscript.log' -print | sort)
test "${#angel_logs[@]}" -eq 1
ANGELSCRIPT_LOG="${angel_logs[0]}"
grep -F "Executing main() in $BATTLE_SCRIPT_NAME(category:CUSTOM" "$ANGELSCRIPT_LOG"
grep -F 'ISS_BATTLE_V81_SCRIPT_MAIN' "$ANGELSCRIPT_LOG"
! grep -Eqi 'failed to build module|exception.*occurred|script was aborted' "$ANGELSCRIPT_LOG"

# First prove two stationary baseline snapshots, then stage B while A is untouched.
pair_ready=0
for _ in $(seq 1 600); do
  grep -Fq 'ISS_BATTLE_SPAWN_FAIL' "$ANGELSCRIPT_LOG" && { cat "$ANGELSCRIPT_LOG" >&2; exit 1; }
  grep -Fq 'ISS_BATTLE_AI_BIND_FAIL' "$ANGELSCRIPT_LOG" && { cat "$ANGELSCRIPT_LOG" >&2; exit 1; }
  if grep -Fq 'ISS_BATTLE_PAIR_READY actors=2' "$ANGELSCRIPT_LOG"; then pair_ready=1; break; fi
  kill -0 "$REAL_ROR_PID" 2>/dev/null || exit 1; sleep 0.1
done
(( pair_ready == 1 ))
for actor in A B; do
  grep -Fq "ISS_NODE_SNAPSHOT_END label=BASE1 actor=$actor" "$ANGELSCRIPT_LOG"
  grep -Fq "ISS_NODE_SNAPSHOT_END label=BASE2 actor=$actor" "$ANGELSCRIPT_LOG"
done
echo 'MULTI_ACTOR_SPAWN_GATE=PASS' | tee artifacts/multi-actor-spawn-gate-v81.txt

# A must still have no real accelerator input while B stages.
! grep -Fq 'ISS_BATTLE_STAGE_FAIL_PLAYER_ACCEL_EARLY' "$ANGELSCRIPT_LOG"
blocker_ready=0
for _ in $(seq 1 600); do
  if grep -Fq 'ISS_BATTLE_BLOCKER_GEOMETRY_FAIL' "$ANGELSCRIPT_LOG"; then cat "$ANGELSCRIPT_LOG" >&2; exit 1; fi
  if grep -Fq 'ISS_BATTLE_BLOCKER_READY ' "$ANGELSCRIPT_LOG"; then blocker_ready=1; break; fi
  kill -0 "$REAL_ROR_PID" 2>/dev/null || exit 1; sleep 0.1
done
(( blocker_ready == 1 ))
grep -F 'ISS_BATTLE_STAGE_ACTIVE player_accel=0' "$ANGELSCRIPT_LOG"
grep -F 'ISS_BATTLE_BLOCKER_READY ' "$ANGELSCRIPT_LOG" | tail -1 | tee artifacts/blocker-ready-v81.txt
grep -Fq 'ISS_NODE_SNAPSHOT_END label=STAGE1 actor=B' "$ANGELSCRIPT_LOG"
grep -Fq 'ISS_NODE_SNAPSHOT_END label=STAGE2 actor=B' "$ANGELSCRIPT_LOG"
echo 'STAGED_BLOCKER_GATE=PASS' | tee artifacts/staged-blocker-gate-v81.txt

xwininfo -root -tree > artifacts/logs/xwininfo-tree-v81.txt
ROR_WINDOW_ID="$(awk '/"Rigs of Rods version/ {print $1; exit}' artifacts/logs/xwininfo-tree-v81.txt)"
test -n "$ROR_WINDOW_ID"
xdotool windowfocus --sync "$ROR_WINDOW_ID"; sleep 0.5
focused="$(printf '0x%x' "$(xdotool getwindowfocus)")"
[[ "${ROR_WINDOW_ID,,}" == "${focused,,}" ]]
printf 'expected=%s focused=%s\n' "$ROR_WINDOW_ID" "$focused" | tee artifacts/logs/window-focus-v81.txt

# Capture begins only after B is physically staged and before A receives real input.
timeout "$((CAPTURE_SECONDS + 15))" ffmpeg -hide_banner -loglevel warning -y -thread_queue_size 512 -f x11grab -draw_mouse 0 -video_size 1280x720 -framerate "$CAPTURE_FPS" -i "$DISPLAY.0" -t "$CAPTURE_SECONDS" -c:v libx264 -preset ultrafast -crf 23 -pix_fmt yuv420p "$BATTLE_VIDEO" > artifacts/logs/ffmpeg-v81.txt 2>&1 &
FFMPEG_PID=$!; sleep 1; kill -0 "$FFMPEG_PID"

xdotool keyup Up; xdotool keydown Up
printf 'BATTLE_INPUT=UP_KEYDOWN_HELD_AFTER_BLOCKER_READY\n' | tee artifacts/battle-input-v81.txt

drive_ack=0
for _ in $(seq 1 300); do
  if grep -Fq 'ISS_BATTLE_PLAYER_DRIVE_ACTIVE accel_ack=1' "$ANGELSCRIPT_LOG"; then drive_ack=1; break; fi
  kill -0 "$REAL_ROR_PID" 2>/dev/null || exit 1; sleep 0.1
done
(( drive_ack == 1 ))
echo 'PLAYER_REAL_INPUT_ACK_GATE=PASS' | tee artifacts/player-input-ack-v81.txt

contact=0
for _ in $(seq 1 300); do
  if grep -Fq 'ISS_BATTLE_CONTACT_DAMAGE_PASS actor=' "$ANGELSCRIPT_LOG"; then contact=1; break; fi
  if grep -Fq 'ISS_BATTLE_FORBIDDEN_RESET' "$ANGELSCRIPT_LOG" || grep -Fq 'ISS_BATTLE_FORBIDDEN_TELEPORT' "$ANGELSCRIPT_LOG"; then cat "$ANGELSCRIPT_LOG" >&2; exit 1; fi
  kill -0 "$REAL_ROR_PID" 2>/dev/null || exit 1; sleep 0.1
done
(( contact == 1 ))
grep -F 'ISS_BATTLE_CONTACT_DAMAGE_PASS actor=' "$ANGELSCRIPT_LOG" | head -1 | tee artifacts/contact-damage-v81.txt
echo 'DIRECT_ENGINE_DAMAGE_EVENT_GATE=PASS' | tee artifacts/direct-damage-event-gate-v81.txt

post_ready=0
for _ in $(seq 1 150); do
  if grep -Fq 'ISS_BATTLE_POST_SNAPSHOT_COMPLETE' "$ANGELSCRIPT_LOG"; then post_ready=1; break; fi
  kill -0 "$REAL_ROR_PID" 2>/dev/null || exit 1; sleep 0.1
done
(( post_ready == 1 ))
xdotool keyup Up
printf 'BATTLE_INPUT=UP_KEYUP_SENT_AFTER_POST\n' | tee -a artifacts/battle-input-v81.txt
sleep 2; kill -0 "$REAL_ROR_PID"

wait "$FFMPEG_PID"; FFMPEG_PID=''
cp "$ANGELSCRIPT_LOG" artifacts/logs/Angelscript-v81-final.log
cp "$ROR_LOG" artifacts/logs/RoR-v81-final.log
cp "$RUNNER_TEMP/ror-v81.stdout.log" artifacts/logs/ror-v81.stdout.log
cp "$RUNNER_TEMP/xvfb-v81.log" artifacts/logs/xvfb-v81.log
! grep -Fq 'ISS_BATTLE_FORBIDDEN_RESET' "$ANGELSCRIPT_LOG"
! grep -Fq 'ISS_BATTLE_FORBIDDEN_TELEPORT' "$ANGELSCRIPT_LOG"
! grep -Eqi 'failed to build module|exception.*occurred|script was aborted' "$ANGELSCRIPT_LOG"
python3 "$GITHUB_WORKSPACE/.github/ror-v81/physics_validator_v81.py" "$ANGELSCRIPT_LOG" > artifacts/battle-physics-evidence-v81.txt
cat artifacts/battle-physics-evidence-v81.txt
echo 'ROR_BATTLE_RUNTIME_V81_GATE=PASS' | tee artifacts/ror-battle-runtime-v81-gate.txt

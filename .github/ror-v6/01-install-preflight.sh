#!/usr/bin/env bash
set -euxo pipefail
sudo apt-get update
sudo apt-get install -y --no-install-recommends \
  ca-certificates curl unzip file python3 procps psmisc coreutils gdb \
  xvfb x11-utils xauth dbus-x11 xdotool ffmpeg mesa-utils \
  libgl1 libgl1-mesa-dri libglx-mesa0 libglu1-mesa \
  libx11-6 libxext6 libxrender1 libxi6 libxrandr2 libxinerama1 \
  libxcursor1 libxfixes3 libfontconfig1 libfreetype6 \
  libopenal1 libpulse0 libgtk-3-0
mkdir -p artifacts/logs artifacts/logs/ldd artifacts/logs/stall-diagnostics
required=(curl unzip file python3 Xvfb xdpyinfo xwininfo xdotool glxinfo glxgears ffmpeg ffprobe ldd sha256sum timeout grep sed awk find sort tee basename stat realpath wc ps tail gdb top)
for cmd in "${required[@]}"; do command -v "$cmd"; done
test "$(uname -m)" = 'x86_64'
sudo -n true
cat /proc/sys/kernel/yama/ptrace_scope | tee artifacts/logs/ptrace-scope.txt
sleep 30 &
GDB_PREFLIGHT_PID=$!
set +e
timeout 10s sudo -n gdb -q -batch -ex 'set pagination off' -ex 'set debuginfod enabled off' -ex 'bt' -p "$GDB_PREFLIGHT_PID" > artifacts/logs/gdb-attach-preflight.txt 2>&1
GDB_PREFLIGHT_RC=$?
set -e
kill -TERM "$GDB_PREFLIGHT_PID" 2>/dev/null || true
wait "$GDB_PREFLIGHT_PID" 2>/dev/null || true
(( GDB_PREFLIGHT_RC == 0 )) || { cat artifacts/logs/gdb-attach-preflight.txt >&2; exit 1; }
grep -Eq '#0|Thread' artifacts/logs/gdb-attach-preflight.txt
echo 'GDB_ATTACH_PREFLIGHT=PASS' | tee artifacts/gdb-attach-preflight-gate.txt
ffmpeg -hide_banner -encoders > artifacts/logs/ffmpeg-encoders.txt 2>&1
grep -E '[[:space:]]libx264[[:space:]]' artifacts/logs/ffmpeg-encoders.txt
ffmpeg -hide_banner -devices > artifacts/logs/ffmpeg-devices.txt 2>&1
grep -F 'x11grab' artifacts/logs/ffmpeg-devices.txt
{
  echo "source_tag=$ROR_SOURCE_TAG_SHA"
  echo "package_sha256=$ROR_ZIP_SHA256"
  echo 'SCRIPT_LOAD_CONTRACT=OgreScriptBuilder strips path to basename and opens through ResourceGroupManager'
  echo 'USER_SCRIPT_RESOURCE_CONTRACT=sys_user_dir/scripts is registered as an OGRE FileSystem resource location'
  echo "PROBE_SCRIPT_NAME=$PROBE_SCRIPT_NAME"
  echo 'TRUCK_ACCELERATE=Keyboard UP'
  echo 'ENGINE_START_CONTRACT=sim_spawn_running(true)->StartEngine()->gear1+DRIVE'
  echo 'GEAR_SELECTION=source_default_DRIVE_no_PageDown_required'
  echo 'telemetry=RoR-2022.12 custom AngelScript frameStep -> getCurrentTruck()->getVehiclePosition()/getSpeed()'
  echo 'accelerator_ack=RoR-2022.12 inputs.getEventBoolValue(EV_TRUCK_ACCELERATE) observed inside frameStep'
  echo 'runtime_readiness=multiple consecutive fresh RoR frameStep samples required before idle acceptance'
  echo 'stall_diagnostics=live per-thread proc snapshots + bounded sudo gdb thread apply all bt full captured before RoR cleanup'
  echo 'motion_gate=horizontal displacement >= 2.0m and driven motion above measured idle baseline using monotonic real intervals'
} > artifacts/logs/source-verified-control-contract.txt

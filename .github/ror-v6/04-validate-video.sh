#!/usr/bin/env bash
set -euxo pipefail
VIDEO='artifacts/ror-motion-e2e.mp4'
test -s "$VIDEO"
grep -F 'SCRIPT_RESOURCE_PATH_GATE=PASS' artifacts/script-resource-path.txt
grep -F 'SCRIPT_RESOURCE_REGISTRATION_GATE=PASS' artifacts/script-resource-registration-gate.txt
grep -F 'SCRIPT_CLI_GATE=PASS' artifacts/script-cli-gate.txt
grep -F 'SCRIPT_BUILD_MAIN_GATE=PASS' artifacts/script-build-main-gate.txt
grep -F 'RUNTIME_READINESS_GATE=CONSECUTIVE_FRESH_FRAMESTEP_PASS' artifacts/runtime-readiness-evidence.txt
grep -F 'TELEMETRY_GATE=ROR_ANGELSCRIPT_ACTOR_POSITION_PASS' artifacts/telemetry-gate.txt
grep -F 'ACCEL_INPUT_TRANSPORT_GATE=ROR_APPLICATION_ACK_PASS' artifacts/input-transport.txt
grep -F 'GEAR_SELECTION=SOURCE_DEFAULT_STARTENGINE_GEAR1_DRIVE_NO_PGDOWN' artifacts/gear-selection.txt
grep -F 'MOTION_GATE=PASS' artifacts/motion-evidence.txt

ffprobe -v error -select_streams v:0 -show_entries stream=codec_name,width,height,avg_frame_rate -show_entries format=duration,size -of default=noprint_wrappers=1 "$VIDEO" | tee artifacts/ffprobe.txt
CODEC="$(ffprobe -v error -select_streams v:0 -show_entries stream=codec_name -of csv=p=0 "$VIDEO")"
DURATION="$(ffprobe -v error -show_entries format=duration -of csv=p=0 "$VIDEO")"
WIDTH="$(ffprobe -v error -select_streams v:0 -show_entries stream=width -of csv=p=0 "$VIDEO")"
HEIGHT="$(ffprobe -v error -select_streams v:0 -show_entries stream=height -of csv=p=0 "$VIDEO")"
FRAMES="$(ffprobe -v error -count_frames -select_streams v:0 -show_entries stream=nb_read_frames -of csv=p=0 "$VIDEO")"
SIZE="$(stat -c '%s' "$VIDEO")"
python3 - "$CODEC" "$DURATION" "$WIDTH" "$HEIGHT" "$FRAMES" "$SIZE" "$CAPTURE_SECONDS" "$CAPTURE_FPS" <<'PY'
import sys
codec=sys.argv[1]; duration=float(sys.argv[2]); width=int(sys.argv[3]); height=int(sys.argv[4]); frames=int(sys.argv[5]); size=int(sys.argv[6]); req=float(sys.argv[7]); fps=float(sys.argv[8])
errors=[]
if codec!='h264': errors.append(f'codec={codec}')
if duration<req-1.0: errors.append(f'duration={duration}')
if (width,height)!=(1280,720): errors.append(f'resolution={width}x{height}')
if frames<int((req-1.0)*fps): errors.append(f'frames={frames}')
if size<=0: errors.append(f'size={size}')
if errors: raise SystemExit('VIDEO_CONTAINER_GATE_FAIL: '+'; '.join(errors))
print('VIDEO_CONTAINER_GATE=PASS')
PY

ffmpeg -hide_banner -v error -i "$VIDEO" -f null -
BLACK_LIMIT="$(python3 - "$DURATION" <<'PY'
import sys
print(max(1.0,float(sys.argv[1])-2.0))
PY
)"
ffmpeg -hide_banner -i "$VIDEO" -vf "blackdetect=d=${BLACK_LIMIT}:pix_th=0.02" -an -f null - >/dev/null 2> artifacts/blackdetect.txt
python3 - artifacts/blackdetect.txt "$DURATION" <<'PY'
import re,sys
from pathlib import Path
duration=float(sys.argv[2]); spans=[float(x) for x in re.findall(r'black_duration:([0-9.]+)',Path(sys.argv[1]).read_text(errors='replace'))]
longest=max(spans,default=0.0); limit=max(1.0,duration-2.0)
if longest>=limit: raise SystemExit(f'VIDEO_BLACK_GATE_FAIL: longest={longest} limit={limit}')
print(f'VIDEO_BLACK_GATE=PASS longest={longest}')
PY

MID="$(python3 - "$DURATION" <<'PY'
import sys
print(float(sys.argv[1])/2.0)
PY
)"
END="$(python3 - "$DURATION" <<'PY'
import sys
print(max(0.0,float(sys.argv[1])-1.0))
PY
)"
ffmpeg -hide_banner -loglevel error -y -ss 1 -i "$VIDEO" -frames:v 1 artifacts/frame-start.png
ffmpeg -hide_banner -loglevel error -y -ss "$MID" -i "$VIDEO" -frames:v 1 artifacts/frame-mid.png
ffmpeg -hide_banner -loglevel error -y -ss "$END" -i "$VIDEO" -frames:v 1 artifacts/frame-end.png
test -s artifacts/frame-start.png
test -s artifacts/frame-mid.png
test -s artifacts/frame-end.png
sha256sum artifacts/frame-start.png artifacts/frame-mid.png artifacts/frame-end.png | tee artifacts/frame-sha256.txt
UNIQUE_FRAME_HASHES="$(awk '{print $1}' artifacts/frame-sha256.txt | sort -u | wc -l)"
(( UNIQUE_FRAME_HASHES >= 2 ))

! grep -Eqi 'Startup error|No render system plugin available|Terrain loading error|Terrain not found:|FATAL ERROR' artifacts/logs/RoR-after-motion.log
! grep -F "exception upon loading script file '$PROBE_SCRIPT_NAME'" artifacts/logs/RoR-after-motion.log
! grep -Eqi 'failed to build module|exception.*occurred|script was aborted' artifacts/logs/Angelscript-after-motion.log
grep -F "Executing main() in $PROBE_SCRIPT_NAME(category:CUSTOM" artifacts/logs/Angelscript-after-motion.log
grep -F 'ISS_MOTION_PROBE_V6_SCRIPT_MAIN' artifacts/logs/Angelscript-after-motion.log
awk -v map="$ROR_MAP" -v truck="$ROR_TRUCK" 'index($0,"===== LOADING TERRAIN " map){t=NR} index($0,"[RoR|Diag] Preselected Truck:")&&index($0,truck)&&t{p=NR} index($0,"===== DONE LOADING VEHICLE")&&p&&NR>p{d=NR} END{exit !(t&&p>t&&d>p)}' artifacts/logs/RoR-after-motion.log

{
  echo 'ROR_MOTION_E2E_AUDITED_V6_ACCEPTANCE=PASS'
  echo 'SCRIPT_RESOURCE=USER_SCRIPTS_OGRE_RESOURCE_PASS'
  echo 'SCRIPT_CLI=RUNSCRIPT_BASENAME_CUSTOM_MAIN_PASS'
  echo 'RUNTIME_READINESS=CONSECUTIVE_FRESH_FRAMESTEP_PASS'
  echo 'TELEMETRY=ROR_ANGELSCRIPT_REAL_ACTOR_POSITION_PASS'
  echo 'INPUT_TRANSPORT=FOCUSED_XTEST_UP_WITH_ROR_APPLICATION_ACK_PASS'
  echo 'GEAR=SOURCE_DEFAULT_STARTENGINE_GEAR1_DRIVE_PASS'
  echo 'MOTION=PHYSICAL_POSITION_DISPLACEMENT_GE_2M_REAL_DT_PASS'
  echo 'VIDEO=H264_1280x720_DECODE_PASS'
} | tee artifacts/acceptance.txt

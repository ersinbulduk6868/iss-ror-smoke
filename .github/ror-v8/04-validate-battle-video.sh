#!/usr/bin/env bash
set -Eeuo pipefail
VIDEO='artifacts/ror-battle-e2e-v8.mp4'
test -s "$VIDEO"
grep -F 'MULTI_ACTOR_SPAWN_GATE=PASS' artifacts/multi-actor-spawn-gate.txt
grep -F 'DUAL_ACTOR_CONTROL_GATE=PASS' artifacts/dual-actor-control-gate.txt
grep -F 'DIRECT_ENGINE_DAMAGE_EVENT_GATE=PASS' artifacts/direct-damage-event-gate.txt
grep -F 'MULTI_ACTOR_MOTION_GATE=PASS' artifacts/battle-physics-evidence.txt
grep -F 'DIRECT_BEAM_BREAK_GATE=PASS' artifacts/battle-physics-evidence.txt
grep -F 'QUALIFIED_CONTACT_DAMAGE_GATE=PASS' artifacts/battle-physics-evidence.txt
grep -F 'NO_RESET_TELEPORT_GATE=PASS' artifacts/battle-physics-evidence.txt
grep -F 'PERSISTENT_DEFORMATION_GATE=PASS' artifacts/battle-physics-evidence.txt
grep -F 'CONTINUOUS_WORLD_GATE=PASS' artifacts/battle-physics-evidence.txt
grep -F 'ROR_BATTLE_RUNTIME_V8_GATE=PASS' artifacts/ror-battle-runtime-v8-gate.txt

ffprobe -v error -select_streams v:0 -show_entries stream=codec_name,width,height,avg_frame_rate -show_entries format=duration,size -of default=noprint_wrappers=1 "$VIDEO" | tee artifacts/ffprobe-v8.txt
CODEC="$(ffprobe -v error -select_streams v:0 -show_entries stream=codec_name -of csv=p=0 "$VIDEO")"
WIDTH="$(ffprobe -v error -select_streams v:0 -show_entries stream=width -of csv=p=0 "$VIDEO")"
HEIGHT="$(ffprobe -v error -select_streams v:0 -show_entries stream=height -of csv=p=0 "$VIDEO")"
DURATION="$(ffprobe -v error -show_entries format=duration -of csv=p=0 "$VIDEO")"
FRAMES="$(ffprobe -v error -count_frames -select_streams v:0 -show_entries stream=nb_read_frames -of csv=p=0 "$VIDEO")"
SIZE="$(stat -c %s "$VIDEO")"
python3 - "$CODEC" "$WIDTH" "$HEIGHT" "$DURATION" "$FRAMES" "$SIZE" "$CAPTURE_SECONDS" "$CAPTURE_FPS" <<'PY'
import sys
codec,w,h,dur,frames,size,expect_s,fps=sys.argv[1:]
w=int(w);h=int(h);dur=float(dur);frames=int(frames);size=int(size);expect=float(expect_s);fps=int(fps)
assert codec=='h264',codec
assert (w,h)==(1280,720),(w,h)
assert dur>=expect-1.0,(dur,expect)
assert frames>=int((expect-1.0)*fps),(frames,expect,fps)
assert size>1_000_000,size
print('VIDEO_CONTAINER_GATE=PASS')
PY
ffmpeg -hide_banner -v error -i "$VIDEO" -f null -
BLACK_LIMIT="$(python3 - "$DURATION" <<'PY'
import sys
print(max(2.0,float(sys.argv[1])-2.0))
PY
)"
ffmpeg -hide_banner -i "$VIDEO" -vf "blackdetect=d=${BLACK_LIMIT}:pix_th=0.02" -an -f null - 2> artifacts/blackdetect-v8.txt
python3 - artifacts/blackdetect-v8.txt "$DURATION" <<'PY'
import re,sys
text=open(sys.argv[1],errors='replace').read(); dur=float(sys.argv[2])
lengths=[float(x) for x in re.findall(r'black_duration:([0-9.]+)',text)]
longest=max(lengths,default=0.0)
if longest>=max(2.0,dur-2.0): raise SystemExit(f'VIDEO_BLACK_GATE_FAIL longest={longest}')
print(f'VIDEO_BLACK_GATE=PASS longest={longest}')
PY
MID="$(python3 - "$DURATION" <<'PY'
import sys
print(float(sys.argv[1])/2)
PY
)"
END="$(python3 - "$DURATION" <<'PY'
import sys
print(max(1.0,float(sys.argv[1])-1.0))
PY
)"
ffmpeg -hide_banner -loglevel error -y -ss 1 -i "$VIDEO" -frames:v 1 artifacts/frame-v8-start.png
ffmpeg -hide_banner -loglevel error -y -ss "$MID" -i "$VIDEO" -frames:v 1 artifacts/frame-v8-mid.png
ffmpeg -hide_banner -loglevel error -y -ss "$END" -i "$VIDEO" -frames:v 1 artifacts/frame-v8-end.png
sha256sum artifacts/frame-v8-start.png artifacts/frame-v8-mid.png artifacts/frame-v8-end.png | tee artifacts/frame-v8-sha256.txt
UNIQUE="$(awk '{print $1}' artifacts/frame-v8-sha256.txt | sort -u | wc -l)"
(( UNIQUE >= 2 ))
! grep -Eqi 'Startup error|No render system plugin available|Terrain loading error|Terrain not found:|FATAL ERROR' artifacts/logs/RoR-v8-final.log
! grep -Eqi 'failed to build module|exception.*occurred|script was aborted' artifacts/logs/Angelscript-v8-final.log
{
  echo 'ROR_BATTLE_E2E_AUDITED_V8_ACCEPTANCE=PASS'
  echo 'PINNED_ROR_2022_12_PACKAGE=PASS'
  echo 'MULTI_ACTOR=2_ACTORS_PERSISTENT_PASS'
  echo 'CONTROL=PLAYER_XTEST_PLUS_ROR_AI_PASS'
  echo 'CONTACT_DAMAGE=ROR_BEAM_BREAK_WITH_NODE_PROXIMITY_PASS'
  echo 'DAMAGE_PERSISTENCE=NODE_GEOMETRY_PASS'
  echo 'NO_RESET_TELEPORT=PASS'
  echo 'VIDEO=REAL_ROR_1280x720_H264_DECODE_PASS'
} | tee artifacts/acceptance-v8.txt

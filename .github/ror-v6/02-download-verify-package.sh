#!/usr/bin/env bash
set -euxo pipefail
mkdir -p "$RUNNER_TEMP/ror" "$RUNNER_TEMP/ror-home"
curl -fL --retry 5 --retry-all-errors --retry-delay 3 "$ROR_ZIP_URL" -o "$RUNNER_TEMP/ror.zip"
printf '%s  %s\n' "$ROR_ZIP_SHA256" "$RUNNER_TEMP/ror.zip" | sha256sum -c - | tee artifacts/logs/ror-zip-sha256-check.txt
unzip -t "$RUNNER_TEMP/ror.zip" > artifacts/logs/ror-zip-test.txt
grep -F 'No errors detected' artifacts/logs/ror-zip-test.txt
unzip -q "$RUNNER_TEMP/ror.zip" -d "$RUNNER_TEMP/ror"

ROR_DIR="$RUNNER_TEMP/ror"
ROR_TEST_HOME="$RUNNER_TEMP/ror-home"
if [[ -d "$ROR_DIR/config" ]]; then
  ROR_USER_DIR="$ROR_DIR/config"
else
  ROR_USER_DIR="$ROR_TEST_HOME/.rigsofrods"
fi
ROR_LOG="$ROR_USER_DIR/logs/RoR.log"
ROR_USER_SCRIPTS_DIR="$ROR_USER_DIR/scripts"
PROBE_SCRIPT="$ROR_USER_SCRIPTS_DIR/$PROBE_SCRIPT_NAME"
mkdir -p "$ROR_USER_SCRIPTS_DIR"

{
  echo "ROR_DIR=$ROR_DIR"
  echo "ROR_TEST_HOME=$ROR_TEST_HOME"
  echo "ROR_USER_DIR=$ROR_USER_DIR"
  echo "ROR_USER_SCRIPTS_DIR=$ROR_USER_SCRIPTS_DIR"
  echo "ROR_LOG=$ROR_LOG"
  echo "PROBE_SCRIPT=$PROBE_SCRIPT"
} >> "$GITHUB_ENV"

test -f "$ROR_DIR/RoR" && chmod +x "$ROR_DIR/RoR"
test -f "$ROR_DIR/RunRoR" && chmod +x "$ROR_DIR/RunRoR"
test -f "$ROR_DIR/plugins.cfg"
test -d "$ROR_DIR/lib"
test -d "$ROR_DIR/resources"
test -d "$ROR_DIR/content"
grep -F 'LD_LIBRARY_PATH' "$ROR_DIR/RunRoR"
grep -F './RoR "$@"' "$ROR_DIR/RunRoR"

map_matches=(); truck_matches=()
while IFS= read -r archive; do
  unzip -t "$archive" >/dev/null
  while IFS= read -r entry; do
    [[ "$entry" =~ (^|/)simple2\.terrn2$ ]] && map_matches+=("$archive|$entry")
    [[ "$entry" =~ (^|/).*semi\.truck$ ]] && truck_matches+=("$archive|$entry")
  done < <(unzip -Z1 "$archive")
done < <(find "$ROR_DIR/content" -maxdepth 1 -type f -name '*.zip' -print | sort)
test "${#map_matches[@]}" -eq 1
test "${#truck_matches[@]}" -eq 1
ROR_MAP="$(basename "${map_matches[0]#*|}")"
ROR_TRUCK="$(basename "${truck_matches[0]#*|}")"
{ echo "ROR_MAP=$ROR_MAP"; echo "ROR_TRUCK=$ROR_TRUCK"; } >> "$GITHUB_ENV"
printf 'ROR_MAP=%s\nROR_TRUCK=%s\n' "$ROR_MAP" "$ROR_TRUCK" | tee artifacts/logs/discovered-scene.txt

export LD_LIBRARY_PATH="$ROR_DIR/lib${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
check_ldd() {
  local target="$1" label="$2" out="artifacts/logs/ldd/$2.txt" rc
  set +e; ldd "$target" > "$out" 2>&1; rc=$?; set -e
  (( rc == 0 )) || { cat "$out" >&2; return 1; }
  ! grep -q 'not found' "$out" || { cat "$out" >&2; return 1; }
}
check_ldd "$ROR_DIR/RoR" RoR
plugin_folder="$(awk -F= '/^[[:space:]]*PluginFolder[[:space:]]*=/ {sub(/^[^=]*=/, ""); gsub(/^[[:space:]]+|[[:space:]]+$/, ""); print; exit}' "$ROR_DIR/plugins.cfg")"
test -n "$plugin_folder"
[[ "$plugin_folder" = /* ]] && plugin_base="$plugin_folder" || plugin_base="$ROR_DIR/$plugin_folder"
plugin_base="$(realpath "$plugin_base")"
: > artifacts/logs/resolved-plugins.txt
plugin_count=0
while IFS= read -r line; do
  plugin="${line#*=}"; plugin="${plugin//$'\r'/}"; plugin="$(echo "$plugin" | sed -E 's/^[[:space:]]+//; s/[[:space:]]+$//')"
  [[ -n "$plugin" ]] || continue
  plugin_count=$((plugin_count + 1))
  candidates=("$plugin_base/$plugin"); [[ "$plugin" == *.so || "$plugin" == *.so.* ]] || candidates+=("$plugin_base/${plugin}.so")
  target=''
  for candidate in "${candidates[@]}"; do
    if [[ -f "$candidate" ]]; then [[ -z "$target" ]] || { echo "AMBIGUOUS_PLUGIN: $plugin" >&2; exit 1; }; target="$candidate"; fi
  done
  test -n "$target"
  target="$(realpath "$target")"; label="$(basename "$target" | sed -E 's/[^A-Za-z0-9_.-]+/_/g')"
  echo "Plugin=$plugin -> $target" | tee -a artifacts/logs/resolved-plugins.txt
  check_ldd "$target" "$label"
done < <(grep -E '^[[:space:]]*Plugin[[:space:]]*=' "$ROR_DIR/plugins.cfg")
(( plugin_count > 0 ))

test "$(basename "$PROBE_SCRIPT")" = "$PROBE_SCRIPT_NAME"
test "$(dirname "$PROBE_SCRIPT")" = "$ROR_USER_SCRIPTS_DIR"
cat > "$PROBE_SCRIPT" <<'AS'
int g_probe_seq = 0;
float g_emit_accum = 0.0f;

void main()
{
    log("ISS_MOTION_PROBE_V6_SCRIPT_MAIN");
}

void frameStep(float dt)
{
    g_emit_accum += dt;
    if (g_emit_accum < 0.10f)
        return;
    g_emit_accum = 0.0f;

    BeamClass@ actor = game.getCurrentTruck();
    if (actor == null)
        return;

    vector3 pos = actor.getVehiclePosition();
    int accel = 0;
    if (inputs.getEventBoolValue(EV_TRUCK_ACCELERATE))
        accel = 1;

    log("ISS_MOTION_PROBE_V6 seq=" + g_probe_seq
        + " x=" + pos.x + " y=" + pos.y + " z=" + pos.z
        + " speed=" + actor.getSpeed() + " accel=" + accel);
    g_probe_seq++;
}
AS
cp "$PROBE_SCRIPT" artifacts/logs/iss_motion_probe_v6.as
test -s "$PROBE_SCRIPT"
grep -F 'ISS_MOTION_PROBE_V6_SCRIPT_MAIN' "$PROBE_SCRIPT"
grep -F 'getVehiclePosition()' "$PROBE_SCRIPT"
grep -F 'getEventBoolValue(EV_TRUCK_ACCELERATE)' "$PROBE_SCRIPT"
printf 'SCRIPT_RESOURCE_PATH_GATE=PASS\npath=%s\nname=%s\n' "$PROBE_SCRIPT" "$PROBE_SCRIPT_NAME" | tee artifacts/script-resource-path.txt

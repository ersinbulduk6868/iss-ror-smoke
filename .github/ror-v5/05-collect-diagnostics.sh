#!/usr/bin/env bash
set +e
mkdir -p artifacts/logs
[[ -f "$RUNNER_TEMP/xvfb.log" ]] && cp "$RUNNER_TEMP/xvfb.log" artifacts/logs/xvfb-final.log
[[ -f "$RUNNER_TEMP/ror-runtime.stdout.log" ]] && cp "$RUNNER_TEMP/ror-runtime.stdout.log" artifacts/logs/ror-runtime.stdout-final.log
[[ -n "${ROR_LOG:-}" && -f "$ROR_LOG" ]] && cp "$ROR_LOG" artifacts/logs/RoR-final.log
if [[ -n "${ROR_USER_DIR:-}" && -d "$ROR_USER_DIR" ]]; then
  found_input_map="$(find "$ROR_USER_DIR" -type f -name 'input.map' -print -quit 2>/dev/null)"; [[ -n "$found_input_map" ]] && cp "$found_input_map" artifacts/logs/runtime-input-final.map
  found_as_log="$(find "$ROR_USER_DIR" -type f -name 'Angelscript.log' -print -quit 2>/dev/null)"; [[ -n "$found_as_log" ]] && cp "$found_as_log" artifacts/logs/Angelscript-final.log
  found_probe="$(find "$ROR_USER_DIR" -type f -name "$PROBE_SCRIPT_NAME" -print -quit 2>/dev/null)"; [[ -n "$found_probe" ]] && cp "$found_probe" artifacts/logs/probe-final.as
fi
ps auxww > artifacts/logs/ps-final.txt 2>&1 || true
true

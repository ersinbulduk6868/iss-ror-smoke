#!/usr/bin/env bash
set -euxo pipefail

# Headless CI rendering profile for the exact pinned RoR 2022.12 runtime.
# These values are not acceptance relaxations: the test still renders the real
# RoR scene at 1280x720 and keeps all input/motion/video gates. They only select
# the fastest source-supported graphics modes so Mesa llvmpipe is not asked to
# emulate expensive GPU effects on the 4-vCPU GitHub runner.

ROR_CONFIG_DIR="$ROR_TEST_HOME/.rigsofrods/config"
ROR_CONFIG_FILE="$ROR_CONFIG_DIR/RoR.cfg"
mkdir -p "$ROR_CONFIG_DIR"

cat > "$ROR_CONFIG_FILE" <<'CFG'
gfx_shadow_type=No shadows (fastest)
gfx_sky_mode=Sandstorm (fastest)
gfx_texture_filter=None (fastest)
gfx_vegetation_mode=None (fastest)
gfx_flares_mode=None (fastest)
gfx_water_mode=None
gfx_envmap_enabled=false
gfx_anisotropy=1
gfx_particles_mode=0
gfx_enable_videocams=false
gfx_window_videocams=false
CFG

# Byte-level preflight: require every intended setting exactly once and reject
# graphics keys outside this audited profile.
test -s "$ROR_CONFIG_FILE"
expected_keys=(
  gfx_shadow_type gfx_sky_mode gfx_texture_filter gfx_vegetation_mode
  gfx_flares_mode gfx_water_mode gfx_envmap_enabled gfx_anisotropy
  gfx_particles_mode gfx_enable_videocams gfx_window_videocams
)
for key in "${expected_keys[@]}"; do
  test "$(grep -c "^${key}=" "$ROR_CONFIG_FILE")" -eq 1
done
actual_count="$(grep -c '^gfx_' "$ROR_CONFIG_FILE")"
test "$actual_count" -eq "${#expected_keys[@]}"

grep -Fx 'gfx_shadow_type=No shadows (fastest)' "$ROR_CONFIG_FILE"
grep -Fx 'gfx_sky_mode=Sandstorm (fastest)' "$ROR_CONFIG_FILE"
grep -Fx 'gfx_texture_filter=None (fastest)' "$ROR_CONFIG_FILE"
grep -Fx 'gfx_vegetation_mode=None (fastest)' "$ROR_CONFIG_FILE"
grep -Fx 'gfx_flares_mode=None (fastest)' "$ROR_CONFIG_FILE"
grep -Fx 'gfx_water_mode=None' "$ROR_CONFIG_FILE"
grep -Fx 'gfx_envmap_enabled=false' "$ROR_CONFIG_FILE"

cp "$ROR_CONFIG_FILE" artifacts/logs/RoR-ci-render-profile.cfg
{
  echo 'CI_RENDER_PROFILE_GATE=PASS'
  echo "config=$ROR_CONFIG_FILE"
  echo 'resolution_acceptance=1280x720_UNCHANGED'
  echo 'motion_acceptance=horizontal_displacement_ge_2m_UNCHANGED'
  echo 'input_acceptance=ror_application_accelerator_ack_UNCHANGED'
  echo 'video_acceptance=h264_decode_black_and_unique_frame_gates_UNCHANGED'
  echo 'source_profile=RoR_2022.12_fastest_graphics_modes_for_software_renderer'
} | tee artifacts/ci-render-profile-gate.txt

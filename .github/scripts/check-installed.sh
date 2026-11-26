#!/bin/bash
# Checks an installed toolkit, after ./setup.sh (easy or performance mode) on
# Linux. Used by ci.yml and performance-build.yml. Run from the repository root.
#
#   1. check_dependencies.py passes inside the environment.
#   2. Every program the install provides starts (check_dependencies.py only
#      reports some of them).
#   3. The tests pass inside the environment.
#
# Usage: .github/scripts/check-installed.sh [FFMPEG_VERSION]
#   FFMPEG_VERSION  performance mode: the environment's ffmpeg must report this
#                   version (the one build-scripts/build-ffmpeg.sh compiles).
set -euo pipefail

ENV_NAME="ddd-capture-toolkit"
FFMPEG_VERSION="${1:-}"
in_env() { conda run -n "$ENV_NAME" "$@"; }

echo "::group::check_dependencies.py"
conda run --no-capture-output -n "$ENV_NAME" python check_dependencies.py
echo "::endgroup::"

echo "::group::Installed programs start"
for cmd in "vhs-decode --help" "tape-decode --help" "tbc-video-export --version" \
           "ld-chroma-decoder --version" "ld-dropout-correct --version" "ld-process-vbi --version" \
           "ld-lds-converter --version"; do
    echo "== $cmd"
    out=$(mktemp)
    # shellcheck disable=SC2086
    if ! in_env $cmd > "$out" 2>&1; then
        cat "$out"; echo "::error::'$cmd' did not run"; exit 1
    fi
    head -2 "$out"; rm -f "$out"
done
# The ld-* helpers the decode and export stages run (tool_health.LD_TOOLS) must
# each be the environment's own copy and able to start. tool_health knows both
# ld-ldf-reader flavours (the compiled C reader prints its usage and exits
# non-zero on --help, the Python one does not), so ask it rather than run them.
in_env python -c '
import sys, tool_health
bad = []
for report in tool_health.check_ld_tools():
    lines, severity = tool_health.format_report(report)
    print("\n".join(lines))
    if severity != "ok":
        bad.append(report["name"])
sys.exit(f"not OK: {bad}" if bad else 0)
' || { echo "::error::an ld-* helper is missing, outside the environment or cannot start"; exit 1; }
# ld-analyse is a graphical viewer and cannot start without a display.
in_env sh -c 'command -v ld-analyse' || { echo "::error::ld-analyse is not installed"; exit 1; }
echo "::endgroup::"

if [[ -n "$FFMPEG_VERSION" ]]; then
    echo "::group::Compiled FFmpeg"
    line=$(in_env sh -c "\"\$CONDA_PREFIX/bin/ffmpeg\" -hide_banner -version" | head -1)
    echo "$line"
    [[ "$line" == "ffmpeg version ${FFMPEG_VERSION} "* ]] || { echo "::error::expected the compiled FFmpeg ${FFMPEG_VERSION}"; exit 1; }
    in_env sh -c "\"\$CONDA_PREFIX/bin/ffmpeg\" -hide_banner -version" | grep -q -- '--enable-libsoxr' \
        || { echo "::error::the compiled FFmpeg has no libsoxr"; exit 1; }
    echo "::endgroup::"
fi

for t in test_*.py; do
    echo "::group::$t"
    conda run --no-capture-output -n "$ENV_NAME" python "$t"
    echo "::endgroup::"
done
echo "Installed toolkit checks passed."

#!/bin/bash
# build-ldf-reader.sh - compile the C ld-ldf-reader into the conda environment
# Part of DDD Capture Toolkit build system
#
# ld-ldf-reader reads .ldf / .flac RF captures and writes raw 16-bit samples to
# stdout. The toolkit uses it for capture analysis and for .ldf validation.
#
# vhs-decode >= 0.4.0 decodes .ldf/.flac itself, in-process through PyAV, and no
# longer ships the compiled reader; pip installs a Python script of the same name
# instead. This builds the original C reader from the pinned external/ld-decode
# source (one C file) and installs it over that script, linked against the
# environment's FFmpeg with an rpath to the environment's lib folder so it keeps
# starting without LD_LIBRARY_PATH. The toolkit handles either command-line style
# (see tool_health.ldf_reader_argv), so a later 'pip install --upgrade vhs-decode'
# putting the Python script back is harmless.
#
# Run it AFTER vhs-decode and FFmpeg are installed: after vhs-decode so this
# copy is the one left in bin/, after FFmpeg so it is linked against the final
# libraries.

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

source "${SCRIPT_DIR}/common/conda-setup.sh"

show_usage() {
    echo "Usage: $0 [OPTIONS]"
    echo ""
    echo "Compile ld-ldf-reader from external/ld-decode into the conda environment"
    echo ""
    echo "OPTIONS:"
    echo "  --safe      Use safe optimizations (no -march=native)"
    echo "  --help      Show this help message"
}

SAFE_MODE=false
while [[ $# -gt 0 ]]; do
    case "$1" in
        --safe) SAFE_MODE=true; shift ;;
        --jobs) shift 2 ;;      # accepted so setup.sh can pass the same arguments to every build script
        --clean) shift ;;
        --help|-h) show_usage; exit 0 ;;
        *) log_error "Unknown option: $1"; show_usage; exit 1 ;;
    esac
done

log_info "=== ld-ldf-reader build (C, from ld-decode) ==="

setup_build_environment || exit 1

SRC="${PROJECT_ROOT}/external/ld-decode/tools/ld-ldf-reader/ld-ldf-reader.c"
if [[ ! -f "$SRC" ]]; then
    log_error "ld-ldf-reader source not found: $SRC"
    log_error "Make sure git submodules are initialised (git submodule update --init external/ld-decode)"
    exit 1
fi

if [[ -z "${CONDA_PREFIX:-}" ]]; then
    log_error "CONDA_PREFIX is not set"
    exit 1
fi

export PKG_CONFIG_PATH="${CONDA_PREFIX}/lib/pkgconfig:${PKG_CONFIG_PATH:-}"
PKG_CONFIG_BIN="${CONDA_PREFIX}/bin/pkg-config"
[[ -x "$PKG_CONFIG_BIN" ]] || PKG_CONFIG_BIN="pkg-config"

if ! "$PKG_CONFIG_BIN" --exists libavcodec libavformat libavutil; then
    log_error "FFmpeg development files (libavcodec, libavformat, libavutil) not found in ${CONDA_PREFIX}"
    exit 1
fi

if [[ "$SAFE_MODE" == "true" ]]; then
    OPT_FLAGS=$("${SCRIPT_DIR}/common/optimize-flags.sh" --cflags --safe)
else
    OPT_FLAGS=$("${SCRIPT_DIR}/common/optimize-flags.sh" --cflags)
fi
log_info "Using optimization flags: $OPT_FLAGS"

# Compile with the system compiler, not the conda cross-compiler in $CC. The
# performance FFmpeg in the environment is built with the system gcc against the
# system C library, so its libavcodec needs symbols (for example log10f@GLIBC_2.43)
# that conda's older-glibc linker cannot resolve: 'undefined reference ... GLIBC_2.43'.
CC_BIN="$(command -v gcc || true)"
if [[ -z "$CC_BIN" || "$CC_BIN" == "${CONDA_PREFIX}"/* ]]; then
    CC_BIN="$(command -v cc || true)"
fi
if [[ -z "$CC_BIN" ]]; then
    log_error "No system C compiler (gcc) found. Install one, e.g. sudo dnf install gcc"
    exit 1
fi
log_info "Using compiler: $CC_BIN"
OUT="${CONDA_PREFIX}/bin/ld-ldf-reader"
TMP_OUT="$(mktemp "${CONDA_PREFIX}/bin/.ld-ldf-reader.XXXXXX")"

# shellcheck disable=SC2046
if ! "$CC_BIN" $OPT_FLAGS -o "$TMP_OUT" "$SRC" \
        $("$PKG_CONFIG_BIN" --cflags --libs libavcodec libavformat libavutil) \
        -Wl,-rpath,"${CONDA_PREFIX}/lib"; then
    rm -f "$TMP_OUT"
    log_error "Compiling ld-ldf-reader failed"
    exit 1
fi
chmod 755 "$TMP_OUT"
mv -f "$TMP_OUT" "$OUT"

# It must start on its own, without LD_LIBRARY_PATH, or the build is no use.
if env -u LD_LIBRARY_PATH -u DYLD_LIBRARY_PATH "$OUT" 2>&1 | grep -qE "error while loading shared libraries|Library not loaded"; then
    log_error "ld-ldf-reader was built but cannot find its libraries without LD_LIBRARY_PATH"
    exit 1
fi

log_success "ld-ldf-reader installed: $OUT"

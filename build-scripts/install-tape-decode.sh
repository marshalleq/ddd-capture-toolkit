#!/bin/bash
# install-tape-decode.sh - install namazso/tape-decode-rs, the Rust decoder (Linux and macOS)
# Part of DDD Capture Toolkit build system
#
# tape-decode is a Rust port of vhs-decode. The toolkit can use it as its decoder
# ("decoder_backend": "tape-decode" in config/config.json, see decoder_backends.py).
#
#   --mode easy         download the newest release binary for this CPU (Linux x86-64 only:
#                       x86-64-v1 .. v4, the highest level the CPU supports)
#   --mode performance  clone the source and compile it for this CPU (needs cargo; Linux and macOS)
#
# Either way a 'tape-decode' command ends up in the conda environment's bin/.
#
# Usage: install-tape-decode.sh --mode easy|performance [--version TAG|latest] [--safe]
#                               [--prefix DIR] [--dest DIR]
#   --version  easy: release tag (default: newest release)
#              performance: git tag, branch or commit (default: the default branch)
#   --safe     performance: no -C target-cpu=native
#   --prefix   environment to put the command in (default: $CONDA_PREFIX)
#   --dest     where source / downloads are kept (default: <toolkit>/external/tape-decode
#              for source, <toolkit>/tools for downloads)

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
source "${SCRIPT_DIR}/common/conda-setup.sh"

REPO="namazso/tape-decode-rs"
MODE=""
VERSION="latest"
SAFE=false
PREFIX="${CONDA_PREFIX:-}"
DEST=""

while [[ $# -gt 0 ]]; do
    case "$1" in
        --mode)    MODE="$2"; shift 2 ;;
        --version) VERSION="$2"; shift 2 ;;
        --safe)    SAFE=true; shift ;;
        --prefix)  PREFIX="$2"; shift 2 ;;
        --dest)    DEST="$2"; shift 2 ;;
        --jobs)    shift 2 ;;      # accepted so setup.sh can pass the same arguments to every build script
        --clean)   shift ;;
        --help|-h) sed -n '2,22p' "$0"; exit 0 ;;
        *) log_error "Unknown option: $1"; exit 1 ;;
    esac
done

if [[ "$MODE" != "easy" && "$MODE" != "performance" ]]; then
    log_error "--mode easy or --mode performance is required"; exit 1
fi
case "$(uname -s)" in
    Linux) ;;
    Darwin)
        if [[ "$MODE" == "easy" ]]; then
            log_error "There is no prebuilt tape-decode for macOS. Use ./setup.sh --performance, which builds it for your Mac."
            exit 1
        fi ;;
    *) log_error "tape-decode is installed on Linux and macOS by this script."; exit 1 ;;
esac
if [[ -z "$PREFIX" || ! -d "$PREFIX/bin" ]]; then
    log_error "No environment to install into (use --prefix, or activate the conda environment)"; exit 1
fi

if [[ "$MODE" == "easy" ]]; then
    [[ "$(uname -m)" == "x86_64" ]] || {
        log_error "The tape-decode release binaries are x86-64 only. On $(uname -m) use ./setup.sh --performance"; exit 1; }
    command -v curl &> /dev/null || { log_error "curl is needed to download tape-decode"; exit 1; }
    PY="${PREFIX}/bin/python"; [[ -x "$PY" ]] || PY="$(command -v python3)"

    if [[ "$VERSION" == "latest" ]]; then
        LOCATION="$(curl -fsSLI -o /dev/null -w '%{url_effective}' "https://github.com/${REPO}/releases/latest")"
        VERSION="${LOCATION##*/}"
        if [[ -z "$VERSION" || "$VERSION" == "latest" ]]; then
            log_error "Could not work out the newest tape-decode release"; exit 1
        fi
    fi

    # Highest x86-64 level this CPU supports
    flags=" $(grep -m1 '^flags' /proc/cpuinfo) "
    has() { for f in "$@"; do [[ "$flags" == *" $f "* ]] || return 1; done; }
    LEVEL=v1
    has ssse3 sse4_1 sse4_2 popcnt && LEVEL=v2
    has ssse3 sse4_1 sse4_2 popcnt avx avx2 bmi1 bmi2 fma movbe && LEVEL=v3
    [[ $LEVEL == v3 ]] && has avx512f avx512bw avx512cd avx512dq avx512vl && LEVEL=v4
    log_info "tape-decode ${VERSION}, x86-64-${LEVEL} build"

    DEST="${DEST:-${PROJECT_ROOT}/tools}"
    WORK="$(mktemp -d "${TMPDIR:-/tmp}/tape-decode.XXXXXX")"
    trap 'rm -rf "$WORK"' EXIT
    curl -fL --progress-bar -o "${WORK}/linux.tar.xz" \
        "https://github.com/${REPO}/releases/download/${VERSION}/linux.tar.xz" \
        || { log_error "Download failed (is there a linux.tar.xz asset on release ${VERSION}?)"; exit 1; }
    tar -xJf "${WORK}/linux.tar.xz" -C "$WORK"
    BIN="${WORK}/x86-64-${LEVEL}/tape-decode"
    [[ -f "$BIN" ]] || { log_error "The release has no x86-64-${LEVEL} build"; exit 1; }
    mkdir -p "$DEST"
    install -m 755 "$BIN" "${DEST}/tape-decode-${VERSION}"
    ln -sf "${DEST}/tape-decode-${VERSION}" "${PREFIX}/bin/tape-decode"
    for old in "${DEST}"/tape-decode-*; do
        [[ "$old" == "${DEST}/tape-decode-${VERSION}" ]] || rm -f "$old"
    done
    log_success "tape-decode ${VERSION} (x86-64-${LEVEL}) installed: ${PREFIX}/bin/tape-decode"
    exit 0
fi

# --- performance: build from source ---
command -v cargo &> /dev/null || { log_error "cargo (Rust) is needed to build tape-decode"; exit 1; }
command -v git &> /dev/null || { log_error "git is needed to fetch the tape-decode source"; exit 1; }
SRC="${DEST:-${PROJECT_ROOT}/external/tape-decode}"
if [[ -d "${SRC}/.git" ]]; then
    git -C "$SRC" fetch -q --tags origin
else
    rm -rf "$SRC"
    git clone -q "https://github.com/${REPO}" "$SRC"
fi
if [[ "$VERSION" == "latest" ]]; then
    git -C "$SRC" checkout -q "origin/$(git -C "$SRC" symbolic-ref --short refs/remotes/origin/HEAD | sed 's#^origin/##')"
else
    git -C "$SRC" checkout -q "$VERSION"
fi
log_info "Building tape-decode $(git -C "$SRC" describe --tags --always) ($(git -C "$SRC" log -1 --format=%cs))"

# cargo/libgit2 load conda's libiconv, which lacks the _iconv symbol, so build with the
# environment's library path cleared (the same precaution build-vhs-decode.sh takes)
FLAGS=""
$SAFE || FLAGS="-C target-cpu=native"
( cd "$SRC" && env -u LD_LIBRARY_PATH -u DYLD_LIBRARY_PATH RUSTFLAGS="$FLAGS" cargo build --release -p tape-decode-cli ) \
    || { log_error "tape-decode build failed"; exit 1; }
install -m 755 "${SRC}/target/release/tape-decode" "${PREFIX}/bin/tape-decode"
log_success "tape-decode built and installed: ${PREFIX}/bin/tape-decode"

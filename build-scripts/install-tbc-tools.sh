#!/bin/bash
# install-tbc-tools.sh - install upstream's prebuilt tbc-tools bundle (Linux, both modes)
# Part of DDD Capture Toolkit build system
#
# Each vhs-decode release also publishes tbc-tools: the ld-* programs (ld-analyse, the
# viewer; ld-lds-converter; ld-chroma-decoder; ...) built together and packaged as one
# AppImage. This unpacks it into tools/tbc-tools-<release>/ and puts a small command in
# the conda environment's bin/ for every ld-* program the environment does not already
# have, so the toolkit finds them on PATH exactly as it does for compiled ones.
#
#   Easy mode:        supplies all of them (the environment has none).
#   Performance mode: the compiled ones stay; this only adds the rest (ld-analyse).
#
# Usage: install-tbc-tools.sh [--version TAG|latest] [--prefix DIR] [--dest DIR]
#   --version  vhs-decode release tag to take tbc-tools from (default: the newest release)
#   --prefix   environment to put the commands in (default: $CONDA_PREFIX)
#   --dest     where to keep the unpacked bundle (default: <toolkit>/tools)

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
source "${SCRIPT_DIR}/common/conda-setup.sh"

REPO="oyvindln/vhs-decode"
VERSION="latest"
PREFIX="${CONDA_PREFIX:-}"
DEST="${PROJECT_ROOT}/tools"
MARKER="# tbc-tools-release:"

while [[ $# -gt 0 ]]; do
    case "$1" in
        --version) VERSION="$2"; shift 2 ;;
        --prefix)  PREFIX="$2"; shift 2 ;;
        --dest)    DEST="$2"; shift 2 ;;
        --help|-h) sed -n '2,19p' "$0"; exit 0 ;;
        *) log_error "Unknown option: $1"; exit 1 ;;
    esac
done

if [[ "$(uname -s)" != "Linux" ]]; then
    log_error "This installs the Linux bundle only."; exit 1
fi
if [[ -z "$PREFIX" || ! -d "$PREFIX/bin" ]]; then
    log_error "No environment to install into (use --prefix, or activate the conda environment)"; exit 1
fi
if ! command -v curl &> /dev/null; then
    log_error "curl is needed to download tbc-tools"; exit 1
fi

case "$(uname -m)" in
    x86_64)          ARCH="x86_64" ;;
    aarch64|arm64)   ARCH="arm64" ;;
    *) log_error "Unsupported CPU: $(uname -m)"; exit 1 ;;
esac

# Newest release: /releases/latest redirects to the newest non-pre-release tag
if [[ "$VERSION" == "latest" ]]; then
    LOCATION="$(curl -fsSLI -o /dev/null -w '%{url_effective}' "https://github.com/${REPO}/releases/latest")"
    VERSION="${LOCATION##*/}"
    if [[ -z "$VERSION" || "$VERSION" == "latest" ]]; then
        log_error "Could not work out the newest vhs-decode release"; exit 1
    fi
fi

# The bundle is versioned on its own (tbc-tools_v3.2.5_...), so ask the release which one it carries
PY="$(command -v python3 || command -v python || true)"
[[ -x "${PREFIX}/bin/python" ]] && PY="${PREFIX}/bin/python"
if [[ -z "$PY" ]]; then log_error "Python is needed to read the release"; exit 1; fi
ASSET="$(curl -fsSL "https://api.github.com/repos/${REPO}/releases/tags/${VERSION}" \
    | "$PY" -c "
import json, sys
suffix = 'linux_${ARCH}.tar.xz'
names = [a['name'] for a in json.load(sys.stdin).get('assets', [])]
print(next((n for n in names if n.startswith('tbc-tools_') and n.endswith(suffix)), ''))
")" || ASSET=""
if [[ -z "$ASSET" ]]; then
    log_warning "vhs-decode ${VERSION} has no tbc-tools bundle for Linux ${ARCH}; ld-analyse will not be available"
    exit 0
fi
TOOLS_TAG="${ASSET#tbc-tools_}"; TOOLS_TAG="${TOOLS_TAG%%_*}"
log_info "tbc-tools ${TOOLS_TAG} (from vhs-decode release ${VERSION})"

BUNDLE="${DEST}/tbc-tools-${TOOLS_TAG}"
ROOT="${BUNDLE}/squashfs-root"
if [[ -x "${ROOT}/AppRun" ]]; then
    log_info "Already unpacked: ${BUNDLE}"
else
    WORK="$(mktemp -d "${DEST}/.tbc-tools-work.XXXXXX" 2>/dev/null || { mkdir -p "$DEST"; mktemp -d "${DEST}/.tbc-tools-work.XXXXXX"; })"
    trap 'rm -rf "$WORK"' EXIT
    log_info "Downloading ${ASSET} (about 300 MB)..."
    curl -fL --progress-bar -o "${WORK}/bundle.tar.xz" \
        "https://github.com/${REPO}/releases/download/${VERSION}/${ASSET}" \
        || { log_error "Download failed"; exit 1; }
    tar -xJf "${WORK}/bundle.tar.xz" -C "$WORK"
    IMAGE="$(ls "${WORK}"/tbc-tools/*.AppImage 2>/dev/null | head -n1)"
    if [[ -z "$IMAGE" ]]; then log_error "No AppImage inside ${ASSET}"; exit 1; fi
    # Unpack it rather than run it as an AppImage: no FUSE needed, and no per-run mount
    ( cd "${WORK}/tbc-tools" && "$IMAGE" --appimage-extract > /dev/null 2>&1 ) \
        || { log_error "Could not unpack the tbc-tools AppImage"; exit 1; }
    rm -rf "$BUNDLE"; mkdir -p "$BUNDLE"
    mv "${WORK}/tbc-tools/squashfs-root" "$ROOT"
    rm -rf "$WORK"; trap - EXIT
fi
for old in "${DEST}"/tbc-tools-*/; do
    [[ "${old%/}" == "$BUNDLE" ]] || { log_info "Removing older bundle ${old}"; rm -rf "$old"; }
done

# A command for every ld-* program the environment does not already provide
installed=()
kept=()
for tool in "${ROOT}"/usr/bin/ld-*; do
    name="$(basename "$tool")"
    target="${PREFIX}/bin/${name}"
    if [[ -e "$target" ]] && ! grep -q "$MARKER" "$target" 2>/dev/null; then
        kept+=("$name"); continue      # a compiled (or otherwise real) copy is already there
    fi
    cat > "${target}.new" <<EOF
#!/bin/bash
# Written by the DDD Capture Toolkit setup: runs ${name} from upstream's prebuilt tbc-tools release.
${MARKER} ${TOOLS_TAG}
exec "${ROOT}/AppRun" ${name} "\$@"
EOF
    chmod 755 "${target}.new"
    mv -f "${target}.new" "$target"
    installed+=("$name")
done

log_success "tbc-tools ${TOOLS_TAG}: ${#installed[@]} commands installed (${installed[*]})"
[[ ${#kept[@]} -gt 0 ]] && log_info "Kept the environment's own copies of: ${kept[*]}"
exit 0

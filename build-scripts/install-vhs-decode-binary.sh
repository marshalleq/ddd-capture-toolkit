#!/bin/bash
# install-vhs-decode-binary.sh - easy mode: install upstream's prebuilt vhs-decode release
# Part of DDD Capture Toolkit build system
#
# The vhs-decode on PyPI lags the releases (PyPI has 0.3.8.1; the current release is
# v0.4.0) and 0.3.8.1 crashes on its first frame under the NumPy 2 that conda installs.
# Upstream publishes each release as a prebuilt bundle, so easy mode uses that: it is
# the same code performance mode compiles, without the compiling.
#
# Linux: downloads decode_<tag>_linux_<arch>.AppImage into tools/ and writes a small
# 'vhs-decode' command into the conda environment's bin/ that runs it, so the toolkit
# finds 'vhs-decode' on PATH exactly as it does for a compiled install.
#
# Usage: install-vhs-decode-binary.sh [--version TAG|latest] [--prefix DIR] [--dest DIR]
#   --version  release tag, e.g. v0.4.0 (default: the newest release)
#   --prefix   environment to put the vhs-decode command in (default: $CONDA_PREFIX)
#   --dest     where to keep the downloaded bundle (default: <toolkit>/tools)

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
source "${SCRIPT_DIR}/common/conda-setup.sh"

REPO="oyvindln/vhs-decode"
VERSION="latest"
PREFIX="${CONDA_PREFIX:-}"
DEST="${PROJECT_ROOT}/tools"

while [[ $# -gt 0 ]]; do
    case "$1" in
        --version) VERSION="$2"; shift 2 ;;
        --prefix)  PREFIX="$2"; shift 2 ;;
        --dest)    DEST="$2"; shift 2 ;;
        --help|-h) sed -n '2,20p' "$0"; exit 0 ;;
        *) log_error "Unknown option: $1"; exit 1 ;;
    esac
done

if [[ "$(uname -s)" != "Linux" ]]; then
    log_error "This installs the Linux AppImage only. On macOS and Windows use --performance, or"
    log_error "download the release bundle from https://github.com/${REPO}/releases"
    exit 1
fi
if [[ -z "$PREFIX" || ! -d "$PREFIX/bin" ]]; then
    log_error "No environment to install into (use --prefix, or activate the conda environment)"
    exit 1
fi

case "$(uname -m)" in
    x86_64)          ARCH="x86_64" ;;
    aarch64|arm64)   ARCH="arm64" ;;
    *) log_error "Unsupported CPU: $(uname -m)"; exit 1 ;;
esac

fetch() {   # fetch URL OUTPUT
    if command -v curl &> /dev/null; then
        curl -fL --progress-bar -o "$2" "$1"
    elif command -v wget &> /dev/null; then
        wget -O "$2" "$1"
    else
        log_error "Neither curl nor wget found"; return 1
    fi
}

# Resolve the newest release: /releases/latest redirects to the newest non-pre-release tag
if [[ "$VERSION" == "latest" ]]; then
    if ! command -v curl &> /dev/null; then
        log_error "curl is needed to look up the newest release (or pass --version v0.4.0)"; exit 1
    fi
    LOCATION="$(curl -fsSLI -o /dev/null -w '%{url_effective}' "https://github.com/${REPO}/releases/latest")"
    VERSION="${LOCATION##*/}"
    if [[ -z "$VERSION" || "$VERSION" == "latest" ]]; then
        log_error "Could not work out the newest vhs-decode release"; exit 1
    fi
fi
log_info "vhs-decode release: $VERSION"

ASSET="decode_${VERSION}_linux_${ARCH}.AppImage"
URL="https://github.com/${REPO}/releases/download/${VERSION}/${ASSET}"
IMAGE="${DEST}/vhs-decode-${VERSION}.AppImage"
mkdir -p "$DEST"

if [[ -x "$IMAGE" ]]; then
    log_info "Already downloaded: $IMAGE"
else
    log_info "Downloading ${ASSET} (about 300 MB)..."
    fetch "$URL" "${IMAGE}.part" || { rm -f "${IMAGE}.part"; log_error "Download failed: $URL"; exit 1; }
    chmod +x "${IMAGE}.part"
    mv "${IMAGE}.part" "$IMAGE"
fi

# AppImages mount themselves with FUSE. Where FUSE is missing, run them by extracting first.
EXTRACT_LINE=""
if ! "$IMAGE" vhs --help > /dev/null 2>&1; then
    if APPIMAGE_EXTRACT_AND_RUN=1 "$IMAGE" vhs --help > /dev/null 2>&1; then
        log_warning "FUSE is not available, so the bundle will unpack itself on every run (slower to start)."
        log_warning "Installing FUSE 2 (Fedora: fuse-libs, Debian/Ubuntu: libfuse2) avoids that."
        EXTRACT_LINE="export APPIMAGE_EXTRACT_AND_RUN=1"
    else
        log_error "The downloaded bundle does not run: $IMAGE"
        exit 1
    fi
fi

SHIM="${PREFIX}/bin/vhs-decode"
# A pip-installed console script of the same name would be replaced by the command below.
cat > "${SHIM}.new" <<EOF
#!/bin/bash
# Written by the DDD Capture Toolkit setup (easy mode): runs upstream's prebuilt vhs-decode release.
# vhs-decode-release: ${VERSION}
${EXTRACT_LINE}
exec "${IMAGE}" vhs "\$@"
EOF
chmod 755 "${SHIM}.new"
mv -f "${SHIM}.new" "$SHIM"

if "$SHIM" --help > /dev/null 2>&1; then
    log_success "vhs-decode ${VERSION} installed: ${SHIM}"
else
    log_error "The vhs-decode command was written but does not run: ${SHIM}"
    exit 1
fi

# ld-ldf-reader: the toolkit runs it for capture analysis and .ldf validation. The release
# ships it as a Python script that needs PyAV, so install PyAV and fetch that script for
# this tag. (It is a single standalone file.) Performance mode compiles the C reader instead.
PY="${PREFIX}/bin/python"
if [[ -x "$PY" ]]; then
    READER="${PREFIX}/bin/ld-ldf-reader"
    READER_URL="https://raw.githubusercontent.com/${REPO}/${VERSION}/lddecode/ldf_reader.py"
    log_info "Installing ld-ldf-reader (PyAV and the ${VERSION} reader script)..."
    if "$PY" -m pip install -q av \
        && fetch "$READER_URL" "${READER}.part" \
        && { printf '#!%s\n' "$PY"; cat "${READER}.part"; } > "${READER}.new" \
        && chmod 755 "${READER}.new" \
        && mv -f "${READER}.new" "$READER"; then
        rm -f "${READER}.part"
        if "$READER" --help > /dev/null 2>&1; then
            log_success "ld-ldf-reader installed: ${READER}"
        else
            log_warning "ld-ldf-reader was written but does not run: ${READER}"
        fi
    else
        rm -f "${READER}.part" "${READER}.new"
        log_warning "Could not install ld-ldf-reader. Capture analysis of .ldf files and .ldf validation need it."
    fi
fi

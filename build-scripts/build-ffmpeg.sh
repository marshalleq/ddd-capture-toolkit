#!/bin/bash
# build-ffmpeg.sh - FFmpeg compilation script with native optimizations
# Part of DDD Capture Toolkit build system
#
# Compiles FFmpeg from source with CPU-specific optimizations for better
# encoding/decoding performance. Uses libraries from conda environment.

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

# Source common utilities
source "${SCRIPT_DIR}/common/conda-setup.sh"

# FFmpeg version to build
FFMPEG_VERSION="7.1"
FFMPEG_URL="https://ffmpeg.org/releases/ffmpeg-${FFMPEG_VERSION}.tar.xz"

show_usage() {
    echo "Usage: $0 [OPTIONS]"
    echo ""
    echo "Build FFmpeg from source with native CPU optimizations"
    echo ""
    echo "OPTIONS:"
    echo "  --safe      Use safe optimizations (no -march=native)"
    echo "  --jobs N    Number of parallel build jobs (default: auto-detect)"
    echo "  --clean     Clean build directory before building"
    echo "  --help      Show this help message"
}

build_ffmpeg() {
    local safe_mode="$1"
    local build_jobs="$2"
    local clean_build="$3"

    log_info "Building FFmpeg from source with native optimizations..."

    # Check if we should skip (already have optimized build)
    if command -v ffmpeg >/dev/null 2>&1; then
        local current_config=$(ffmpeg -buildconf 2>&1 || true)
        if echo "$current_config" | grep -q "march=native"; then
            log_success "FFmpeg already built with native optimizations, skipping"
            return 0
        fi
    fi

    # Install build dependencies via conda (install individually so failures don't block others)
    log_info "Installing FFmpeg build dependencies..."
    local deps=("nasm" "x264" "x265" "libvpx" "libopus" "libvorbis" "lame")
    for dep in "${deps[@]}"; do
        if ! conda list "$dep" 2>/dev/null | grep -q "^$dep "; then
            log_info "Installing $dep..."
            conda install -y -c conda-forge "$dep" 2>/dev/null || log_warning "Failed to install $dep (optional)"
        fi
    done

    # Create build directory in project root (not in any submodule)
    local build_base="${PROJECT_ROOT}/build"
    local build_dir="${build_base}/ffmpeg-${FFMPEG_VERSION}"
    local source_dir="${build_base}/ffmpeg-source"

    mkdir -p "$build_base"

    # Clean if requested
    if [[ "$clean_build" == "true" ]]; then
        log_info "Cleaning existing FFmpeg build..."
        rm -rf "$build_dir" "$source_dir"
    fi

    # Download FFmpeg source if needed
    if [[ ! -d "$source_dir" ]]; then
        log_info "Downloading FFmpeg ${FFMPEG_VERSION}..."
        local tarball="${build_base}/ffmpeg-${FFMPEG_VERSION}.tar.xz"

        if [[ ! -f "$tarball" ]]; then
            curl -L -o "$tarball" "$FFMPEG_URL" || {
                log_error "Failed to download FFmpeg source"
                return 1
            }
        fi

        log_info "Extracting FFmpeg source..."
        tar -xf "$tarball" -C "$build_base"
        # Rename extracted directory to source_dir (don't mkdir first or mv puts it inside)
        mv "${build_base}/ffmpeg-${FFMPEG_VERSION}" "$source_dir"
    fi

    cd "$source_dir"
    log_info "Building in: $(pwd)"

    # Generate optimization flags
    local extra_cflags=""
    local extra_ldflags=""

    if [[ "$safe_mode" == "true" ]]; then
        log_info "Using safe optimization flags (portable build)"
        extra_cflags="-O3"
    else
        log_info "Using native optimization flags (CPU-specific build)"
        extra_cflags="-O3 -march=native -mtune=native"
    fi

    # Add conda library paths
    extra_cflags="$extra_cflags -I${CONDA_PREFIX}/include"
    extra_ldflags="-L${CONDA_PREFIX}/lib -Wl,-rpath,${CONDA_PREFIX}/lib"

    log_info "CFLAGS: $extra_cflags"
    log_info "LDFLAGS: $extra_ldflags"

    # Configure FFmpeg
    # Core features needed for VHS archival workflow:
    # - FFV1: lossless video (built-in)
    # - FLAC: lossless audio (built-in)
    # - MKV: container format (built-in)
    # - x264/x265: for optional lossy exports
    log_info "Configuring FFmpeg..."

    # Set PKG_CONFIG to find conda libraries
    export PKG_CONFIG_PATH="${CONDA_PREFIX}/lib/pkgconfig:${PKG_CONFIG_PATH:-}"

    ./configure \
        --prefix="${CONDA_PREFIX}" \
        --extra-cflags="$extra_cflags" \
        --extra-ldflags="$extra_ldflags" \
        --enable-gpl \
        --enable-version3 \
        --enable-nonfree \
        --enable-pthreads \
        --enable-zlib \
        --enable-libx264 \
        --enable-libx265 \
        --enable-libvpx \
        --enable-libopus \
        --enable-libvorbis \
        --enable-libmp3lame \
        --enable-libsoxr \
        --enable-vaapi \
        --enable-shared \
        --disable-static \
        --disable-doc \
        --disable-debug \
        || {
            log_error "FFmpeg configure failed"
            log_info "Trying minimal configuration..."

            # Fallback: minimal config with just essential features.
            # libsoxr is REQUIRED (final-mux audio resampling uses it). If
            # this minimal configure fails too, the build aborts rather
            # than producing an ffmpeg that silently lacks soxr.
            ./configure \
                --prefix="${CONDA_PREFIX}" \
                --extra-cflags="$extra_cflags" \
                --extra-ldflags="$extra_ldflags" \
                --enable-gpl \
                --enable-pthreads \
                --enable-zlib \
                --enable-libsoxr \
                --enable-shared \
                --disable-static \
                --disable-doc \
                --disable-debug \
                || {
                    log_error "FFmpeg minimal configure also failed"
                    log_error "(libsoxr is required; install soxr-devel or ensure conda 'soxr' package is present)"
                    return 1
                }
        }

    # Build
    log_info "Building FFmpeg (using $build_jobs parallel jobs)..."
    log_info "This may take 10-30 minutes..."
    make -j"$build_jobs" || {
        log_error "FFmpeg build failed"
        return 1
    }

    # Install to conda environment
    log_info "Installing FFmpeg to conda environment..."
    make install || {
        log_error "FFmpeg installation failed"
        return 1
    }

    # Verify installation
    if [[ -x "${CONDA_PREFIX}/bin/ffmpeg" ]]; then
        log_success "FFmpeg successfully installed to ${CONDA_PREFIX}/bin/"

        # Verify native optimizations
        log_info "Verifying FFmpeg build configuration..."
        local new_config=$("${CONDA_PREFIX}/bin/ffmpeg" -buildconf 2>&1 || true)
        if echo "$new_config" | grep -q "march=native"; then
            log_success "FFmpeg built with native CPU optimizations"
        elif [[ "$safe_mode" == "true" ]]; then
            log_success "FFmpeg built with safe optimizations (as requested)"
        else
            log_warning "FFmpeg installed but native optimizations not detected"
        fi

        # Show version
        "${CONDA_PREFIX}/bin/ffmpeg" -version | head -3
    else
        log_error "FFmpeg installation verification failed"
        return 1
    fi

    return 0
}

# Parse command line arguments
SAFE_MODE=false
BUILD_JOBS=""
CLEAN_BUILD=false

while [[ $# -gt 0 ]]; do
    case "$1" in
        --safe)
            SAFE_MODE=true
            shift
            ;;
        --jobs)
            if [[ -z "$2" ]] || [[ "$2" =~ ^- ]]; then
                log_error "--jobs requires a number"
                exit 1
            fi
            BUILD_JOBS="$2"
            shift 2
            ;;
        --clean)
            CLEAN_BUILD=true
            shift
            ;;
        --help|-h)
            show_usage
            exit 0
            ;;
        *)
            log_error "Unknown option: $1"
            show_usage
            exit 1
            ;;
    esac
done

# Set default build jobs if not specified
if [[ -z "$BUILD_JOBS" ]]; then
    BUILD_JOBS=$(get_build_jobs)
fi

log_info "=== FFmpeg Build Script ==="
log_info "Safe mode: $SAFE_MODE"
log_info "Build jobs: $BUILD_JOBS"
log_info "Clean build: $CLEAN_BUILD"
echo ""

# Set up build environment
setup_build_environment || exit 1

echo ""
log_info "Starting FFmpeg build process..."

# Build FFmpeg
build_ffmpeg "$SAFE_MODE" "$BUILD_JOBS" "$CLEAN_BUILD" || {
    log_error "FFmpeg build failed"
    exit 1
}

log_success "FFmpeg build completed successfully!"

#!/bin/bash
# build-ld-decode.sh - LD-Tools compilation script (from vhs-decode)
# Part of DDD Capture Toolkit build system
#
# NOTE: This builds ld-tools from the vhs-decode repository (oyvindln/vhs-decode)
# which has the --input-json option required by tbc-video-export.
# The mainline ld-decode (happycube/ld-decode) uses --input-metadata instead.

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

# Source common utilities
source "${SCRIPT_DIR}/common/conda-setup.sh"

show_usage() {
    echo "Usage: $0 [OPTIONS]"
    echo ""
    echo "Build LD-Tools from vhs-decode source with optimizations"
    echo ""
    echo "OPTIONS:"
    echo "  --safe      Use safe optimizations (no -march=native)"
    echo "  --jobs N    Number of parallel build jobs (default: auto-detect)"
    echo "  --clean     Clean build directory before building"
    echo "  --help      Show this help message"
    echo ""
    echo "Examples:"
    echo "  $0                # Build with native optimizations"
    echo "  $0 --safe         # Build with safe optimizations"
    echo "  $0 --jobs 4       # Build with 4 parallel jobs"
}

build_ld_decode() {
    local safe_mode="$1"
    local build_jobs="$2"
    local clean_build="$3"

    log_info "Building LD-Tools from vhs-decode source..."

    # Check if we need to build (using ld-chroma-decoder as it's required for tbc-video-export)
    # We check for --input-json support to ensure we have the correct version
    if command -v ld-chroma-decoder >/dev/null 2>&1; then
        if ld-chroma-decoder --help 2>&1 | grep -q "input-json"; then
            log_success "LD-Tools with --input-json support already installed, skipping build"
            return 0
        else
            log_warning "Found ld-chroma-decoder but it lacks --input-json support (wrong version)"
            log_info "Will rebuild from vhs-decode source..."
        fi
    fi

    # Navigate to source directory - use vhs-decode which has --input-json
    local ld_decode_dir="${PROJECT_ROOT}/external/vhs-decode"
    if [[ ! -d "$ld_decode_dir" ]]; then
        log_error "vhs-decode source directory not found: $ld_decode_dir"
        log_error "Make sure git submodules are properly initialized"
        return 1
    fi

    cd "$ld_decode_dir"
    log_info "Building in: $(pwd)"

    # Initialize nested submodules (ezpwd for efm-decoder)
    if [[ ! -f "tools/efm-decoder/libs/ezpwd/rs_base" ]]; then
        log_info "Initializing nested submodules..."
        git submodule update --init --recursive
    fi

    # Create and enter build directory (use separate dir to avoid conflict with vhs-decode's Python build)
    local build_dir="build-ld-tools"
    if [[ "$clean_build" == "true" ]] && [[ -d "$build_dir" ]]; then
        log_info "Cleaning existing build directory..."
        rm -rf "$build_dir"
    fi

    mkdir -p "$build_dir"
    cd "$build_dir"

    # Generate optimization flags
    local opt_flags
    if [[ "$safe_mode" == "true" ]]; then
        opt_flags=$("${SCRIPT_DIR}/common/optimize-flags.sh" --cflags --safe)
    else
        opt_flags=$("${SCRIPT_DIR}/common/optimize-flags.sh" --cflags)
    fi

    log_info "Using optimization flags: $opt_flags"

    # Configure with CMake
    log_info "Configuring LD-Tools with CMake..."
    
    # Force library search to prioritize conda environment
    export LD_LIBRARY_PATH="${CONDA_PREFIX}/lib:${LD_LIBRARY_PATH:-}"
    export LIBRARY_PATH="${CONDA_PREFIX}/lib:${LIBRARY_PATH:-}"
    export CMAKE_LIBRARY_PATH="${CONDA_PREFIX}/lib"
    
    # Ensure compilers are explicitly set for CMake
    local cmake_c_compiler="${CMAKE_C_COMPILER:-${CC:-gcc}}"
    local cmake_cxx_compiler="${CMAKE_CXX_COMPILER:-${CXX:-g++}}"
    
    log_info "Using C compiler: $cmake_c_compiler"
    log_info "Using C++ compiler: $cmake_cxx_compiler"
    
    cmake .. \
        -DCMAKE_INSTALL_PREFIX="${CONDA_PREFIX}" \
        -DCMAKE_BUILD_TYPE=Release \
        -DCMAKE_C_COMPILER="$cmake_c_compiler" \
        -DCMAKE_CXX_COMPILER="$cmake_cxx_compiler" \
        -DCMAKE_CXX_FLAGS="$opt_flags" \
        -DCMAKE_C_FLAGS="$opt_flags" \
        -DCMAKE_PREFIX_PATH="${CONDA_PREFIX}" \
        -DCMAKE_FIND_ROOT_PATH="${CONDA_PREFIX}" \
        -DCMAKE_LIBRARY_PATH="${CONDA_PREFIX}/lib" \
        -DCMAKE_INCLUDE_PATH="${CONDA_PREFIX}/include" \
        -DPKG_CONFIG_EXECUTABLE="${CONDA_PREFIX}/bin/pkg-config" \
        -DCMAKE_FIND_LIBRARY_SUFFIXES=".so;.a" \
        -DUSE_QWT=OFF || {
        log_error "CMake configuration failed"
        return 1
    }
    
    # Build
    log_info "Building LD-Tools (using $build_jobs parallel jobs)..."
    make -j"$build_jobs" all || {
        log_error "Build failed"
        return 1
    }

    # Install to conda environment
    log_info "Installing LD-Tools to conda environment..."
    make install || {
        log_error "Installation failed"
        return 1
    }

    # Verify installation - check for ld-chroma-decoder with --input-json support
    if [[ -x "${CONDA_PREFIX}/bin/ld-chroma-decoder" ]]; then
        log_success "LD-Tools successfully installed to ${CONDA_PREFIX}/bin/"

        # Test the installation and verify --input-json support
        log_info "Verifying LD-Tools installation..."
        if "${CONDA_PREFIX}/bin/ld-chroma-decoder" --help 2>&1 | grep -q "input-json"; then
            log_success "LD-Tools installation verified (--input-json support confirmed)"
        else
            log_error "ld-chroma-decoder installed but lacks --input-json support"
            log_error "This indicates the wrong version was built - check source directory"
            return 1
        fi
    else
        log_error "LD-Tools installation verification failed"
        log_error "Expected tool ld-chroma-decoder not found in ${CONDA_PREFIX}/bin/"
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

log_info "=== LD-Tools Build Script (from vhs-decode) ==="
log_info "Safe mode: $SAFE_MODE"
log_info "Build jobs: $BUILD_JOBS"
log_info "Clean build: $CLEAN_BUILD"
echo ""

# Set up build environment
setup_build_environment || exit 1

echo ""
log_info "Starting LD-Tools build process..."

# Build LD-Tools
build_ld_decode "$SAFE_MODE" "$BUILD_JOBS" "$CLEAN_BUILD" || {
    log_error "LD-Tools build failed"
    exit 1
}

log_success "LD-Tools build completed successfully!"

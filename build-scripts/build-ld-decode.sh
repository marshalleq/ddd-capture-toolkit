#!/bin/bash
# build-ld-decode.sh - LD-Decode compilation script
# Part of DDD Capture Toolkit build system

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

# Source common utilities
source "${SCRIPT_DIR}/common/conda-setup.sh"

show_usage() {
    echo "Usage: $0 [OPTIONS]"
    echo ""
    echo "Build LD-Decode from source with optimizations"
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
    
    log_info "Building LD-Decode from source..."
    
    # Check if we need to build (using ld-decode-ntsc as it's a core non-GUI tool)
    if ! needs_build "LD-Decode" "ld-decode-ntsc"; then
        log_success "LD-Decode already installed, skipping build"
        return 0
    fi
    
    # Navigate to source directory
    local ld_decode_dir="${PROJECT_ROOT}/external/ld-decode"
    if [[ ! -d "$ld_decode_dir" ]]; then
        log_error "LD-Decode source directory not found: $ld_decode_dir"
        log_error "Make sure git submodules are properly initialized"
        return 1
    fi
    
    cd "$ld_decode_dir"
    log_info "Building in: $(pwd)"
    
    # Create and enter build directory
    local build_dir="build"
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
    log_info "Configuring LD-Decode with CMake..."
    
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
    log_info "Building LD-Decode (using $build_jobs parallel jobs)..."
    make -j"$build_jobs" all || {
        log_error "Build failed"
        return 1
    }
    
    # Install to conda environment
    log_info "Installing LD-Decode to conda environment..."
    make install || {
        log_error "Installation failed"
        return 1
    }
    
    # Verify installation (check for ld-chroma-decoder which doesn't depend on qwt)
    if [[ -x "${CONDA_PREFIX}/bin/ld-chroma-decoder" ]]; then
        log_success "LD-Decode successfully installed to ${CONDA_PREFIX}/bin/"
        
        # Test the installation
        log_info "Testing LD-Decode installation..."
        if "${CONDA_PREFIX}/bin/ld-chroma-decoder" --help >/dev/null 2>&1; then
            log_success "LD-Decode installation verified"
        else
            log_warning "LD-Decode installed but --help failed (may be normal)"
        fi
    else
        log_error "LD-Decode installation verification failed"
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

log_info "=== LD-Decode Build Script ==="
log_info "Safe mode: $SAFE_MODE"
log_info "Build jobs: $BUILD_JOBS" 
log_info "Clean build: $CLEAN_BUILD"
echo ""

# Set up build environment
setup_build_environment || exit 1

echo ""
log_info "Starting LD-Decode build process..."

# Build LD-Decode
build_ld_decode "$SAFE_MODE" "$BUILD_JOBS" "$CLEAN_BUILD" || {
    log_error "LD-Decode build failed"
    exit 1
}

log_success "LD-Decode build completed successfully!"

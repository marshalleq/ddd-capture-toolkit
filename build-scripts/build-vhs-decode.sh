#!/bin/bash
# build-vhs-decode.sh - VHS-Decode compilation script
# Part of DDD Capture Toolkit build system

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

# Source common utilities
source "${SCRIPT_DIR}/common/conda-setup.sh"

show_usage() {
    echo "Usage: $0 [OPTIONS]"
    echo ""
    echo "Build VHS-Decode from source with optimizations"
    echo ""
    echo "OPTIONS:"
    echo "  --safe      Use safe optimizations (no -march=native)"
    echo "  --jobs N    Number of parallel build jobs (default: auto-detect)"
    echo "  --clean     Clean build directory before building"
    echo "  --help      Show this help message"
}

build_vhs_decode() {
    local safe_mode="$1"
    local build_jobs="$2"
    local clean_build="$3"
    
    log_info "Building VHS-Decode from source..."
    
    # Check if we need to build
    if ! needs_build "VHS-Decode" "vhs-decode"; then
        log_success "VHS-Decode already installed, skipping build"
        return 0
    fi
    
    # Navigate to source directory
    local vhs_decode_dir="${PROJECT_ROOT}/external/vhs-decode"
    if [[ ! -d "$vhs_decode_dir" ]]; then
        log_error "VHS-Decode source directory not found: $vhs_decode_dir"
        log_error "Make sure git submodules are properly initialized"
        return 1
    fi
    
    cd "$vhs_decode_dir"
    log_info "Building in: $(pwd)"
    
    # VHS-Decode uses Rust and pip for installation
    log_info "Installing VHS-Decode with pip..."
    
    # Install Rust if not available (VHS-Decode requires it)
    if ! command -v cargo >/dev/null 2>&1; then
        log_warning "Rust/Cargo not found. VHS-Decode requires Rust."
        log_warning "Install Rust from: https://rustup.rs/"
        log_warning "Or use conda: conda install rust"
        return 1
    fi
    
    # Install VHS-Decode using pip (which will compile from source)
    log_info "Installing VHS-Decode requirements..."
    pip install -r requirements.txt || {
        log_error "Failed to install Python requirements"
        return 1
    }
    
    # Install VHS-Decode itself
    log_info "Installing VHS-Decode (this may take several minutes)..."
    pip install . || {
        log_error "VHS-Decode installation failed"
        return 1
    }
    
    # Verify installation
    if command -v vhs-decode >/dev/null 2>&1; then
        log_success "VHS-Decode successfully installed"
        
        # Test the installation
        log_info "Testing VHS-Decode installation..."
        if vhs-decode --help >/dev/null 2>&1; then
            log_success "VHS-Decode installation verified"
        else
            log_warning "VHS-Decode installed but --help failed (may be normal)"
        fi
    else
        log_error "VHS-Decode installation verification failed"
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

log_info "=== VHS-Decode Build Script ==="
log_info "Safe mode: $SAFE_MODE (Note: VHS-Decode uses Rust, optimization flags may not apply)"
log_info "Build jobs: $BUILD_JOBS"
log_info "Clean build: $CLEAN_BUILD"
echo ""

# Set up build environment
setup_build_environment || exit 1

echo ""
log_info "Starting VHS-Decode build process..."

# Build VHS-Decode
build_vhs_decode "$SAFE_MODE" "$BUILD_JOBS" "$CLEAN_BUILD" || {
    log_error "VHS-Decode build failed"
    exit 1
}

log_success "VHS-Decode build completed successfully!"

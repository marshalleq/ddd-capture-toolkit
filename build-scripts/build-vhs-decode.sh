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
    echo "  --version V Specify vhs-decode version to build (default: latest release tag)"
    echo "              Use 'latest' for bleeding edge (latest commit)"
    echo "              Use a specific tag like 'v0.3.8' or 'tools_prerelease'"
    echo "  --help      Show this help message"
}

# Fetch the latest release tag from the vhs-decode repository
get_latest_release_tag() {
    local vhs_decode_dir="$1"
    cd "$vhs_decode_dir"

    # Fetch all tags from remote
    git fetch --tags origin 2>/dev/null || {
        log_warning "Could not fetch tags from remote"
        return 1
    }

    # vhs-decode uses various tag formats: 0.3.8.1, v0.3.5, etc.
    # Get tags sorted by creation date and filter for version-like patterns
    local latest_tag
    # First try tags that look like version numbers (with or without 'v' prefix)
    # Exclude tags like 'rust_merge' that aren't versions
    latest_tag=$(git tag -l --sort=-creatordate 2>/dev/null | grep -E '^v?[0-9]+\.[0-9]+' | head -n1)

    if [[ -z "$latest_tag" ]]; then
        # Fallback: try any tag sorted by date
        latest_tag=$(git tag -l --sort=-creatordate 2>/dev/null | head -n1)
    fi

    if [[ -z "$latest_tag" ]]; then
        log_warning "No release tags found"
        return 1
    fi

    echo "$latest_tag"
}

# Get information about available versions
show_version_info() {
    local vhs_decode_dir="$1"
    cd "$vhs_decode_dir"

    log_info "Fetching version information from vhs-decode repository..."
    git fetch --tags origin 2>/dev/null || true
    git fetch origin 2>/dev/null || true

    echo ""
    log_info "Available vhs-decode versions:"

    # Show latest release tags (version-like tags sorted by date)
    local latest_tags
    latest_tags=$(git tag -l --sort=-creatordate 2>/dev/null | grep -E '^v?[0-9]+\.[0-9]+' | head -n5)
    if [[ -n "$latest_tags" ]]; then
        echo "  Recent release tags:"
        echo "$latest_tags" | while read -r tag; do
            local tag_date
            tag_date=$(git log -1 --format="%ci" "$tag" 2>/dev/null | cut -d' ' -f1)
            echo "    $tag ($tag_date)"
        done
    fi

    # Show latest commit on main branch
    local main_branch="vhs_decode"
    local latest_commit
    latest_commit=$(git log -1 origin/$main_branch --format="%h %ci %s" 2>/dev/null | head -c80)
    if [[ -n "$latest_commit" ]]; then
        echo "  Latest commit (bleeding edge):"
        echo "    $latest_commit"
    fi

    echo ""
}

# Checkout the specified version
checkout_version() {
    local vhs_decode_dir="$1"
    local version="$2"

    cd "$vhs_decode_dir"

    # Fetch latest from remote
    log_info "Fetching latest code from vhs-decode repository..."
    git fetch --tags origin 2>/dev/null || log_warning "Could not fetch from remote"
    git fetch origin 2>/dev/null || true

    if [[ "$version" == "latest" ]]; then
        # Checkout latest commit on main branch (bleeding edge)
        local main_branch="vhs_decode"
        log_info "Checking out latest commit (bleeding edge) from $main_branch branch..."
        git checkout "origin/$main_branch" 2>/dev/null || {
            log_error "Could not checkout origin/$main_branch"
            return 1
        }
    else
        # Checkout specific tag/version
        log_info "Checking out version: $version"
        git checkout "$version" 2>/dev/null || {
            log_error "Could not checkout version: $version"
            log_error "Available tags:"
            git tag -l | head -n10
            return 1
        }
    fi

    # Show what we checked out
    local current_ref
    current_ref=$(git describe --tags --always 2>/dev/null || git rev-parse --short HEAD)
    local commit_date
    commit_date=$(git log -1 --format="%ci" | cut -d' ' -f1)
    log_success "Checked out: $current_ref ($commit_date)"

    return 0
}

build_vhs_decode() {
    local safe_mode="$1"
    local build_jobs="$2"
    local clean_build="$3"
    local target_version="$4"

    log_info "Building VHS-Decode from source..."

    # Navigate to source directory
    local vhs_decode_dir="${PROJECT_ROOT}/external/vhs-decode"
    if [[ ! -d "$vhs_decode_dir" ]]; then
        log_error "VHS-Decode source directory not found: $vhs_decode_dir"
        log_error "Make sure git submodules are properly initialized"
        return 1
    fi

    cd "$vhs_decode_dir"
    log_info "Building in: $(pwd)"

    # Determine which version to build
    if [[ -z "$target_version" ]]; then
        # Auto-detect latest release tag
        log_info "No version specified, detecting latest release tag..."
        target_version=$(get_latest_release_tag "$vhs_decode_dir")
        if [[ -z "$target_version" ]]; then
            log_warning "Could not determine latest release tag, using current submodule state"
            target_version=""
        else
            log_info "Latest release tag: $target_version"
        fi
    fi

    # Checkout the target version if specified
    if [[ -n "$target_version" ]]; then
        checkout_version "$vhs_decode_dir" "$target_version" || {
            log_error "Failed to checkout version: $target_version"
            return 1
        }
    else
        # Just show current state
        local current_ref
        current_ref=$(git describe --tags --always 2>/dev/null || git rev-parse --short HEAD)
        log_info "Using current submodule state: $current_ref"
    fi

    echo ""

    # Set optimization flags for Cython compilation
    if [[ "$safe_mode" == "true" ]]; then
        log_info "Using safe optimization flags (portable build)"
        export CFLAGS="-O3 ${CFLAGS:-}"
        export CXXFLAGS="-O3 ${CXXFLAGS:-}"
    else
        log_info "Using native optimization flags (CPU-specific build)"
        export CFLAGS="-O3 -march=native -mtune=native ${CFLAGS:-}"
        export CXXFLAGS="-O3 -march=native -mtune=native ${CXXFLAGS:-}"
    fi
    log_info "CFLAGS: $CFLAGS"
    log_info "CXXFLAGS: $CXXFLAGS"

    # Configure Numba for optimal performance
    export NUMBA_CPU_NAME="native"
    log_info "NUMBA_CPU_NAME: $NUMBA_CPU_NAME"

    # VHS-Decode requires Rust for the performance-critical vhsd_rust extension
    if ! command -v cargo >/dev/null 2>&1; then
        log_error "Rust/Cargo not found. VHS-Decode requires Rust for the vhsd_rust extension."
        log_error "Install Rust from: https://rustup.rs/"
        return 1
    else
        # Set Rust optimization flags for native CPU
        if [[ "$safe_mode" == "true" ]]; then
            export RUSTFLAGS="-C opt-level=3 ${RUSTFLAGS:-}"
        else
            export RUSTFLAGS="-C target-cpu=native -C opt-level=3 ${RUSTFLAGS:-}"
        fi
        log_info "RUSTFLAGS: $RUSTFLAGS"
    fi

    # Install setuptools-rust (required to build the Rust extension)
    log_info "Installing build dependencies..."
    pip install setuptools-rust || {
        log_error "Failed to install setuptools-rust"
        return 1
    }

    # Install VHS-Decode using pip (which will compile from source with our flags)
    log_info "Installing VHS-Decode requirements..."
    pip install -r requirements.txt || {
        log_error "Failed to install Python requirements"
        return 1
    }

    # Force reinstall to ensure recompilation with our flags
    log_info "Installing VHS-Decode with optimizations (this may take several minutes)..."
    pip install --no-build-isolation --force-reinstall . || {
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
TARGET_VERSION=""

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
        --version)
            if [[ -z "$2" ]] || [[ "$2" =~ ^- ]]; then
                log_error "--version requires a value (e.g., 'latest', 'v0.3.8')"
                exit 1
            fi
            TARGET_VERSION="$2"
            shift 2
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
if [[ -n "$TARGET_VERSION" ]]; then
    log_info "Target version: $TARGET_VERSION"
else
    log_info "Target version: auto-detect (latest release tag)"
fi
echo ""

# Set up build environment
setup_build_environment || exit 1

echo ""
log_info "Starting VHS-Decode build process..."

# Build VHS-Decode
build_vhs_decode "$SAFE_MODE" "$BUILD_JOBS" "$CLEAN_BUILD" "$TARGET_VERSION" || {
    log_error "VHS-Decode build failed"
    exit 1
}

log_success "VHS-Decode build completed successfully!"

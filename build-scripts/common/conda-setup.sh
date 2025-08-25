#!/bin/bash
# conda-setup.sh - Conda environment setup utilities
# Part of DDD Capture Toolkit build system

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check if conda is available and working
check_conda() {
    if ! command -v conda >/dev/null 2>&1; then
        log_error "Conda is not installed or not in PATH"
        log_error "Please install Miniconda or Anaconda first"
        return 1
    fi
    
    # Initialize conda for bash if needed
    if ! conda info >/dev/null 2>&1; then
        log_info "Initialising conda for bash..."
        eval "$(conda shell.bash hook)" || {
            log_error "Failed to initialise conda"
            return 1
        }
    fi
    
    log_info "Conda detected: $(conda --version)"
    return 0
}

# Check if the DDD environment exists and is properly configured
check_ddd_environment() {
    local env_name="ddd-capture-toolkit"
    
    if ! conda info --envs | grep -q "${env_name}"; then
        log_error "Environment '${env_name}' does not exist"
        log_error "Please run setup.sh first to create the environment"
        return 1
    fi
    
    log_info "Environment '${env_name}' found"
    return 0
}

# Activate the DDD environment
activate_ddd_environment() {
    local env_name="ddd-capture-toolkit"
    
    log_info "Activating environment '${env_name}'..."
    
    # Check if already activated
    if [[ "${CONDA_DEFAULT_ENV}" == "${env_name}" ]]; then
        log_info "Environment '${env_name}' already active"
        return 0
    fi
    
    # Initialize conda for bash if not already done
    if ! conda info >/dev/null 2>&1; then
        log_info "Initialising conda for bash..."
        eval "$(conda shell.bash hook)" || {
            log_error "Failed to initialise conda"
            return 1
        }
    fi
    
    # Activate the environment
    conda activate "${env_name}" || {
        log_error "Failed to activate environment '${env_name}'"
        return 1
    }
    
    log_success "Environment '${env_name}' activated"
    log_info "CONDA_PREFIX: ${CONDA_PREFIX}"
    return 0
}

# Verify conda environment is properly set up for building
verify_build_environment() {
    if [[ -z "${CONDA_PREFIX}" ]]; then
        log_error "CONDA_PREFIX is not set - environment not properly activated"
        return 1
    fi
    
    # Check for essential build tools
    local missing_tools=()
    
    if ! command -v cmake >/dev/null 2>&1; then
        missing_tools+=("cmake")
    fi
    
    if ! command -v make >/dev/null 2>&1; then
        missing_tools+=("make")
    fi
    
    # Check for compiler (gcc, clang, or MSVC)
    local has_compiler=false
    if command -v gcc >/dev/null 2>&1 || command -v clang >/dev/null 2>&1 || command -v cl >/dev/null 2>&1; then
        has_compiler=true
    fi
    
    if ! $has_compiler; then
        missing_tools+=("compiler (gcc/clang/MSVC)")
    fi
    
    if [[ ${#missing_tools[@]} -gt 0 ]]; then
        log_warning "Missing build tools in environment: ${missing_tools[*]}"
        log_warning "These may need to be installed for successful compilation"
    fi
    
    log_success "Build environment verification complete"
    log_info "Install prefix: ${CONDA_PREFIX}"
    
    return 0
}

# Set up build environment variables
setup_build_vars() {
    # Export standard build variables
    export CMAKE_PREFIX_PATH="${CONDA_PREFIX}"
    export CMAKE_INSTALL_PREFIX="${CONDA_PREFIX}"
    export PKG_CONFIG_PATH="${CONDA_PREFIX}/lib/pkgconfig:${PKG_CONFIG_PATH:-}"
    export LD_LIBRARY_PATH="${CONDA_PREFIX}/lib:${LD_LIBRARY_PATH:-}"
    
    # Set up conda compilers explicitly
    setup_conda_compilers
    
    # Platform-specific library paths
    case "$(uname -s)" in
        Darwin*)
            export DYLD_LIBRARY_PATH="${CONDA_PREFIX}/lib:${DYLD_LIBRARY_PATH:-}"
            ;;
        Linux*)
            export LD_LIBRARY_PATH="${CONDA_PREFIX}/lib:${LD_LIBRARY_PATH:-}"
            ;;
    esac
    
    log_info "Build environment variables set"
}

# Configure conda compilers for CMake and other build tools
setup_conda_compilers() {
    local cc_path=""
    local cxx_path=""
    local detected_compilers=()
    
    # Check for conda-provided compilers first
    if [[ -x "${CONDA_PREFIX}/bin/x86_64-conda-linux-gnu-gcc" ]]; then
        cc_path="${CONDA_PREFIX}/bin/x86_64-conda-linux-gnu-gcc"
        cxx_path="${CONDA_PREFIX}/bin/x86_64-conda-linux-gnu-g++"
        detected_compilers+=("conda-gcc")
    elif [[ -x "${CONDA_PREFIX}/bin/x86_64-conda-linux-gnu-c++" ]]; then
        # Handle case where conda uses different naming
        cc_path="${CONDA_PREFIX}/bin/x86_64-conda-linux-gnu-gcc"
        cxx_path="${CONDA_PREFIX}/bin/x86_64-conda-linux-gnu-c++"
        detected_compilers+=("conda-gcc-alt")
    elif [[ -x "${CONDA_PREFIX}/bin/gcc" ]]; then
        cc_path="${CONDA_PREFIX}/bin/gcc"
        cxx_path="${CONDA_PREFIX}/bin/g++"
        detected_compilers+=("conda-gcc-generic")
    elif [[ -x "${CONDA_PREFIX}/bin/clang" ]]; then
        cc_path="${CONDA_PREFIX}/bin/clang"
        cxx_path="${CONDA_PREFIX}/bin/clang++"
        detected_compilers+=("conda-clang")
    fi
    
    # If no conda compilers found, check system compilers
    if [[ -z "$cc_path" ]] && command -v gcc > /dev/null 2>&1; then
        cc_path=$(command -v gcc)
        cxx_path=$(command -v g++)
        detected_compilers+=("system-gcc")
    elif [[ -z "$cc_path" ]] && command -v clang > /dev/null 2>&1; then
        cc_path=$(command -v clang)
        cxx_path=$(command -v clang++)
        detected_compilers+=("system-clang")
    fi
    
    if [[ -n "$cc_path" ]] && [[ -n "$cxx_path" ]]; then
        export CC="$cc_path"
        export CXX="$cxx_path"
        export CMAKE_C_COMPILER="$cc_path"
        export CMAKE_CXX_COMPILER="$cxx_path"
        
        log_info "Configured compilers: ${detected_compilers[*]}"
        log_info "  CC: $CC"
        log_info "  CXX: $CXX"
        
        # Verify compilers work
        if ! "$CC" --version > /dev/null 2>&1; then
            log_warning "C compiler '$CC' does not respond to --version"
        fi
        if ! "$CXX" --version > /dev/null 2>&1; then
            log_warning "C++ compiler '$CXX' does not respond to --version"
        fi
    else
        log_warning "No suitable C/C++ compiler found in conda environment or system"
        log_warning "Build may fail - please install gcc_linux-64/gxx_linux-64 or equivalent"
    fi
}

# Get number of CPU cores for parallel builds
get_build_jobs() {
    local jobs=1
    
    # Try different methods to detect CPU cores
    if command -v nproc >/dev/null 2>&1; then
        jobs=$(nproc)
    elif command -v sysctl >/dev/null 2>&1; then
        jobs=$(sysctl -n hw.ncpu 2>/dev/null || echo "1")
    elif [[ -r /proc/cpuinfo ]]; then
        jobs=$(grep -c ^processor /proc/cpuinfo)
    fi
    
    # Limit to reasonable number for stability
    if [[ $jobs -gt 8 ]]; then
        jobs=8
    fi
    
    echo "$jobs"
}

# Check if a specific tool needs to be built
needs_build() {
    local tool_name="$1"
    local binary_name="$2"
    
    if [[ -z "$tool_name" ]] || [[ -z "$binary_name" ]]; then
        log_error "needs_build requires tool_name and binary_name arguments"
        return 1
    fi
    
    # Check if binary exists in conda environment
    if [[ -x "${CONDA_PREFIX}/bin/${binary_name}" ]]; then
        log_info "${tool_name} already installed in environment"
        return 1  # No build needed
    fi
    
    log_info "${tool_name} needs to be built"
    return 0  # Build needed
}

# Main setup function - call this from build scripts
setup_build_environment() {
    log_info "Setting up build environment..."
    
    check_conda || return 1
    check_ddd_environment || return 1
    
    # Skip activation if CONDA_PREFIX is already set by parent
    if [[ -z "${CONDA_PREFIX}" ]]; then
        activate_ddd_environment || return 1
    else
        log_info "Using conda environment from parent: ${CONDA_PREFIX}"
        # Ensure the conda environment bin directory is in PATH
        if [[ ":$PATH:" != *":${CONDA_PREFIX}/bin:"* ]]; then
            export PATH="${CONDA_PREFIX}/bin:${PATH}"
            log_info "Added conda environment bin directory to PATH"
        fi
    fi
    
    verify_build_environment || return 1
    setup_build_vars || return 1
    
    log_success "Build environment ready"
    return 0
}

# If script is run directly, set up the environment
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    setup_build_environment
fi
